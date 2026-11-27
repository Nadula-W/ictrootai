import {test, expect, Page} from '@playwright/test';

async function workspace(page: Page, mode: 'mcq' | 'retry' | 'short' | 'teacher' = 'mcq') {
  const submitted: {value: string; request_id: string}[] = [];
  const reviews: unknown[] = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data: unknown = [];
    let status = 200;
    if (path === '/api/me') data = {id: mode === 'teacher' ? 2 : 1, name: 'QA Learner', email: 'qa@example.invalid', role: mode === 'teacher' ? 'teacher' : 'student', grade: 12, language: 'en'};
    else if (path === '/api/curriculum') data = {versions: [], units: [{id: 3, name: 'Data Representation', grade: 12, verified: true, levels: [], outcomes: [{id: 'verified', level: '3.1', text: 'Converts numbers between bases', verified: true}]}]};
    else if (path === '/api/coverage') data = {outcomes: [], imported_outcomes: 1, covered_outcomes: 1, official_denominator_verified: false};
    else if (path === '/api/practice') data = {questions: [{id: 1, outcome_id: 'verified', kind: mode === 'short' ? 'short' : 'mcq', difficulty: 'easy', prompt: mode === 'short' ? 'Explain binary place value.' : 'Which binary number represents decimal thirteen?', options: mode === 'short' ? [] : [{id: 'A', text: '1110'}, {id: 'B', text: '1101'}, {id: 'C', text: '1100'}, {id: 'D', text: '1111'}]}], message: 'Approved questions are ready.'};
    else if (path === '/api/practice/1/submit') {
      submitted.push(request.postDataJSON());
      if (mode === 'retry' && submitted.length === 1) {status = 503; data = {detail: 'Connection interrupted.'};}
      else data = {id: 77, question_id: 1, outcome_id: 'verified', value: submitted.at(-1)?.value, score: mode === 'short' ? null : 1, pending: mode === 'short', reason: mode === 'short' ? 'Teacher review required' : 'Deterministic mcq comparison', correct_answer: {answer: mode === 'short' ? 'Each place represents a power of two.' : 'B'}, explanation: 'Approved binary explanation: eight plus four plus one.', rubric: mode === 'short' ? [{criterion: 'Explains powers of two', weight: 1}] : [], possible_misconception: null};
    } else if (path === '/api/revision') data = {outcomes: submitted.length ? [{outcome_id: 'verified', text: 'Converts numbers between bases', attempts: 1, marked_attempts: mode === 'short' ? 0 : 1, pending: mode === 'short' ? 1 : 0, recent_accuracy: mode === 'short' ? null : 100, recommended_difficulty: mode === 'short' ? 'easy' : 'hard', next_review_at: '2026-11-29T00:00:00Z', due: false, status: mode === 'short' ? 'Awaiting teacher review' : 'Confident', possible_misconceptions: []}] : [], method: 'A transparent practice heuristic'};
    else if (path === '/api/teacher/practice') data = [{id: 99, student: 'QA Student', prompt: 'Explain binary place value.', value: 'The places double toward the left.', rubric: [{criterion: 'Explains powers of two', weight: 1}], explanation: 'Each place is a power of two.'}];
    else if (path === '/api/teacher/practice/99/review') {reviews.push(request.postDataJSON()); data = {id: 99, score: 1, pending: false};}
    await route.fulfill({status, contentType: 'application/json', body: JSON.stringify(data)});
  });
  await page.goto('/');
  await page.getByRole('button', {name: mode === 'teacher' ? 'Submissions' : 'Recommended practice', exact: true}).click();
  return {submitted, reviews};
}

test('practice hides feedback until submission then shows saved marking material', async ({page}) => {
  const {submitted} = await workspace(page);
  await expect(page.getByRole('heading', {name: 'Which binary number represents decimal thirteen?'})).toBeVisible();
  await expect(page.getByText('Approved binary explanation: eight plus four plus one.', {exact: true})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Submit answer', exact: true})).toBeDisabled();
  await page.locator('.practice-options button').filter({hasText: '1101'}).click();
  await page.getByRole('button', {name: 'Submit answer', exact: true}).click();
  await expect(page.locator('.practice-feedback[aria-label="Practice feedback"]')).toContainText('Score: 100%');
  await expect(page.getByText('Approved binary explanation: eight plus four plus one.', {exact: true})).toBeVisible();
  expect(submitted).toHaveLength(1);
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('practice retry keeps the same answer and request ID after a connection error', async ({page}) => {
  const {submitted} = await workspace(page, 'retry');
  await page.locator('.practice-options button').filter({hasText: '1101'}).click();
  await page.getByRole('button', {name: 'Submit answer', exact: true}).click();
  await expect(page.locator('.practice-error[role="alert"]')).toContainText('Your answer is kept');
  await expect(page.locator('.practice-options button').first()).toBeDisabled();
  await page.getByRole('button', {name: 'Retry answer', exact: true}).click();
  await expect(page.locator('.practice-feedback[aria-label="Practice feedback"]')).toContainText('Score: 100%');
  expect(submitted).toHaveLength(2);
  expect(submitted[0]).toEqual(submitted[1]);
});

test('descriptive practice stays pending and does not display a final percentage', async ({page}) => {
  await workspace(page, 'short');
  await page.getByLabel('Your answer', {exact: true}).fill('Every position has a power of two.');
  await page.getByRole('button', {name: 'Submit answer', exact: true}).click();
  const feedback = page.locator('.practice-feedback[aria-label="Practice feedback"]');
  await expect(feedback).toContainText('Awaiting teacher review');
  await expect(feedback).not.toContainText('Score:');
  await expect(page.getByText('No final marks yet', {exact: false})).toBeVisible();
});

test('teacher can mark pending class practice using a recorded reason', async ({page}) => {
  const {reviews} = await workspace(page, 'teacher');
  await page.locator('.practice-review-item summary').click();
  await page.getByLabel('Practice score (0–1)', {exact: true}).fill('1');
  await page.getByLabel('Reason for practice mark', {exact: true}).fill('The approved powers-of-two criterion is satisfied.');
  await page.getByRole('button', {name: 'Save practice mark', exact: true}).click();
  await expect(page.getByText('Practice mark saved. The decision and reason are recorded in the review history.', {exact: true})).toBeVisible();
  expect(reviews).toEqual([{score: 1, reason: 'The approved powers-of-two criterion is satisfied.'}]);
});
