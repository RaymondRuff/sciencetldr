/**
 * Science TLDR — the mailbox doorbell.
 *
 * Runs in Google Apps Script on the podcast's own Gmail account, on a
 * five-minute timer, and rings GitHub when mail the pipeline cares about has
 * arrived. It is a doorbell, not a gatekeeper: all it does is ask the
 * generate-episode workflow to run now rather than whenever GitHub's
 * scheduler gets round to it.
 *
 * Why it exists. GitHub delivers roughly three scheduled runs a day on this
 * repository, at times of its choosing, and since 2026-11-14 not one of them
 * has landed before 08:00 UTC — which is when the writer routine picks its
 * paper. So an emailed one-off was collected by an afternoon sweep and
 * written the *following* morning: about two days from sending to hearing it.
 * With the doorbell it is minutes. scripts/schedule_health.py has the data.
 *
 * What it is not. It does not parse, judge or label anything. The Python side
 * owns all of that and is the only thing that decides what a message means.
 * A false ring costs one workflow run that finds nothing; a missed ring costs
 * nothing at all, because the daily sweeps still collect the mail. That
 * asymmetry is deliberate — keep it that way if you edit the patterns below.
 *
 * Setup: see README.md beside this file.
 */

// Matches what scripts/pdf_mailbox.py looks for. Those regexes are
// authoritative; these only have to be no stricter.
const WANTED = /^(?:(?:re|fwd?|fw)\s*:\s*)*\s*(?:one[-\s]?off|subscribe)\b/i;
// Deliberately unanchored, exactly as the Python is: somebody leaving is
// likely to hit reply and type it after our own subject line, and that is the
// one request worth never missing.
const LEAVING = /\bunsubscribe\b/i;
const NUMBERED_REPLY = /\[Science TLDR #\d+\]/i;

// Monday's digest send. GitHub's own crons for it were delivered seven to nine
// hours late on 2026-11-16 and not at all on 11-23, so the only punctual clock
// in this system rings for it too. The window sits after the Monday episode
// publishes (about 11:25 UTC) and before six in the morning Pacific, which is
// 14:00 UTC in winter and 13:00 in summer — so noon UTC is before six either
// way. Ringing when the digest has already gone out is harmless: the send
// picks the newest *unsent* digest and otherwise says there is nothing to do.
const DIGEST_DAY = 1; // Monday, as getUTCDay() counts
const DIGEST_FROM_HOUR = 12; // UTC
const DIGEST_UNTIL_HOUR = 14;

// Gmail's own labels, set by the pipeline once it has dealt with a message.
const SEARCH =
  'newer_than:1d -from:me -label:tldr-processed -label:tldr-rejected';
const MAX_THREADS = 25;

/** The five-minute timer calls this. */
function checkMailbox() {
  const props = PropertiesService.getScriptProperties();
  const repo = props.getProperty('GITHUB_REPO');
  const token = props.getProperty('GITHUB_TOKEN');
  if (!repo || !token) {
    console.error('Set GITHUB_REPO and GITHUB_TOKEN in Project Settings → Script Properties.');
    return;
  }

  // Only ring for something that arrived since the last ring. Without this a
  // message waiting its two or three minutes for the sweep would ring again
  // on every tick.
  maybeRingDigest(props, repo, token);

  const seen = Number(props.getProperty('LAST_SEEN') || 0);
  let newest = seen;
  let waiting = 0;

  GmailApp.search(SEARCH, 0, MAX_THREADS).forEach(function (thread) {
    thread.getMessages().forEach(function (message) {
      const when = message.getDate().getTime();
      if (when <= seen) return;
      const subject = message.getSubject() || '';
      if (!WANTED.test(subject) && !LEAVING.test(subject) && !NUMBERED_REPLY.test(subject)) return;
      waiting += 1;
      if (when > newest) newest = when;
    });
  });

  if (!waiting) return;
  console.log('mail waiting: ' + waiting + ' message(s); ringing');
  if (ring(repo, token)) {
    props.setProperty('LAST_SEEN', String(newest));
  }
}

/**
 * Ask for the digest send, once, on a Monday morning.
 *
 * Called from the same five-minute tick as the mailbox check, so pasting this
 * file is enough — the installed trigger still points at checkMailbox and
 * does not need recreating.
 */
function maybeRingDigest(props, repo, token) {
  const now = new Date();
  if (now.getUTCDay() !== DIGEST_DAY) return;
  const hour = now.getUTCHours();
  if (hour < DIGEST_FROM_HOUR || hour >= DIGEST_UNTIL_HOUR) return;
  const today = now.toISOString().slice(0, 10);
  if (props.getProperty('LAST_DIGEST_RING') === today) return;
  console.log('Monday morning: asking for the digest send');
  if (ring(repo, token, 'digest')) {
    props.setProperty('LAST_DIGEST_RING', today);
  }
}

/** POST a repository_dispatch. Returns whether GitHub accepted it. */
function ring(repo, token, eventType) {
  const response = UrlFetchApp.fetch('https://api.github.com/repos/' + repo + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: JSON.stringify({ event_type: eventType || 'mailbox' }),
    muteHttpExceptions: true,
  });
  const code = response.getResponseCode();
  if (code === 204) {
    console.log('dispatched: ' + (eventType || 'mailbox'));
    return true;
  }
  // Left unrecorded on failure, so the next tick tries again.
  console.error('dispatch refused: ' + code + ' ' + response.getContentText().slice(0, 200));
  return false;
}

/** Run once, by hand, to create the five-minute timer. */
function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'checkMailbox') ScriptApp.deleteTrigger(trigger);
  });
  ScriptApp.newTrigger('checkMailbox').timeBased().everyMinutes(5).create();
  console.log('installed: checkMailbox every five minutes');
}

/** Run by hand to check the wiring without waiting for mail. */
function ringNow() {
  const props = PropertiesService.getScriptProperties();
  ring(props.getProperty('GITHUB_REPO'), props.getProperty('GITHUB_TOKEN'));
}

/** Run by hand to send the digest now, whatever day it is. */
function ringDigestNow() {
  const props = PropertiesService.getScriptProperties();
  ring(props.getProperty('GITHUB_REPO'), props.getProperty('GITHUB_TOKEN'), 'digest');
}
