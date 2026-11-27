import {expect, Page, test} from '@playwright/test';

async function reportsWorkspace(page: Page, failOnce = false) {
  const reads: string[] = [];
  let rosterFailed = false;
  let learnerFailed = false;
  const learners = [
    {id: 1, name: 'Sam', email: 'sam@example.invalid', grade: 12, started_assessments: 1, submitted_assessments: 1, marked_answers: 0, pending_answers: 1, accuracy: null},
    {id: 5, name: 'Maya', email: 'maya@example.invalid', grade: 12, started_assessments: 2, submitted_assessments: 2, marked_answers: 4, pending_answers: 1, accuracy: 50},
  ];
  const weak = {outcome_id: 'binary', text: 'Convert numbers between bases', answered: 2, accuracy: 0, pending_answers: 0, recommended_difficulty: 'easy', evidence_notice: 'Limited marked-answer evidence.'};
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let status = 200;
    let data: unknown = [];
    if (path === '/api/me') data = {id: 2, name: 'Fixture Teacher', email: 'teacher@example.invalid', role: 'teacher', grade: 12, language: 'en'};
    else if (path === '/api/classes') data = [{id: 7, name: 'Revision class', grade: 12, code: 'FIXTURE', members: 2}, {id: 8, name: 'New class', grade: 13, code: 'EMPTY', members: 0}];
    else if (path === '/api/curriculum') data = {units: []};
    else if (path === '/api/coverage') data = {outcomes: []};
    else if (path === '/api/classes/7/students') {
      reads.push(path);
      if (failOnce && !rosterFailed) {rosterFailed = true; status = 503; data = {detail: 'Class report is temporarily unavailable.'};}
      else data = {class_id: 7, class_name: 'Revision class', students: learners};
    } else if (path === '/api/classes/8/students') {reads.push(path); data = {class_id: 8, class_name: 'New class', students: []};}
    else if (path === '/api/classes/7/students/1/progress' || path === '/api/classes/7/students/5/progress') {
      reads.push(path);
      if (failOnce && !learnerFailed) {learnerFailed = true; status = 503; data = {detail: 'Learner report is temporarily unavailable.'};}
      else {
        const learner = path.includes('/1/') ? learners[0] : learners[1];
        data = {
          class_id: 7, class_name: 'Revision class', student: learner,
          submitted_assessments: learner.submitted_assessments, marked_answers: learner.marked_answers,
          pending_answers: learner.pending_answers, accuracy: learner.accuracy,
          recommended_difficulty: learner.id === 1 ? 'medium' : 'easy',
          outcomes: learner.id === 1 ? [{...weak, accuracy: null, answered: 0, pending_answers: 1, recommended_difficulty: 'medium'}] : [weak],
          weak_outcomes: learner.id === 1 ? [] : [weak],
          possible_misconceptions: learner.id === 1 ? [] : [{outcome_id: 'binary', label: 'Place value confusion', evidence_count: 2, question_count: 2}],
          accuracy_notice: 'Submitted assessments in this class only; pending teacher marks are excluded from accuracy.',
          misconception_notice: 'These are tentative explanations to discuss with the learner, not a diagnosis.',
        };
      }
    }
    await route.fulfill({status, contentType: 'application/json', body: JSON.stringify(data)});
  });
  await page.goto('/');
  await page.getByRole('button', {name: 'My classes', exact: true}).click();
  await expect(page.getByRole('region', {name: 'Class progress reports', exact: true})).toBeVisible();
  return reads;
}

test('teacher sees unknown marks, revision priorities and tentative patterns on mobile', async ({page}) => {
  await reportsWorkspace(page);
  const reports = page.getByRole('region', {name: 'Class progress reports', exact: true});
  await reports.getByRole('button', {name: "View Sam's progress", exact: true}).click();
  const sam = reports.getByRole('region', {name: "Sam's progress", exact: true});
  await expect(sam).toBeVisible();
  await expect(sam.getByText('Not marked yet', {exact: true}).first()).toBeVisible();
  await expect(sam).not.toContainText('0%');
  await expect(sam).toContainText('Review pending answers in Submissions');
  await reports.getByRole('button', {name: "View Maya's progress", exact: true}).click();
  const maya = reports.getByRole('region', {name: "Maya's progress", exact: true});
  await expect(maya.getByRole('heading', {name: 'Revision priorities', exact: true})).toBeVisible();
  await expect(maya).toContainText('Convert numbers between bases');
  await expect(maya).toContainText('Place value confusion');
  await expect(maya).toContainText('2 responses across 2 questions');
  await expect(maya).toContainText('tentative');
  await expect(maya).toContainText('not a diagnosis');
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('report errors can be retried and switching classes clears the prior learner report', async ({page}) => {
  const reads = await reportsWorkspace(page, true);
  const reports = page.getByRole('region', {name: 'Class progress reports', exact: true});
  await expect(reports.getByRole('alert')).toContainText('Class report is temporarily unavailable.');
  await reports.getByRole('button', {name: 'Retry class report', exact: true}).click();
  await reports.getByRole('button', {name: "View Maya's progress", exact: true}).click();
  await expect(reports.getByRole('alert')).toContainText('Learner report is temporarily unavailable.');
  await reports.getByRole('button', {name: 'Retry learner report', exact: true}).click();
  await expect(reports.getByRole('region', {name: "Maya's progress", exact: true})).toBeVisible();
  await reports.getByLabel('Report class', {exact: true}).selectOption('8');
  await expect(reports).toContainText('No learners have joined this class yet.');
  await expect(reports.getByRole('region', {name: "Maya's progress", exact: true})).toHaveCount(0);
  expect(reads.every(path => /^\/api\/classes\/(7|8)\/students(?:\/(1|5)\/progress)?$/.test(path))).toBeTruthy();
});
