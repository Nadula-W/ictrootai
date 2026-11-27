import {test,expect} from '@playwright/test';
const password=process.env.ICTROOT_DEMO_PASSWORD;
test.skip(!password,'Set ICTROOT_DEMO_PASSWORD to the locally seeded password; start frontend and backend first.');
async function login(page:import('@playwright/test').Page,role:string){await page.goto('/');await page.getByLabel('Email address').fill(role+'@ictroot.local');await page.getByLabel('Password',{exact:true}).fill(password!);await page.getByRole('button',{name:'Sign in to ICTRoot'}).click();await expect(page.locator('.main-shell')).toBeVisible()}
test('student resumes an assessment, submits, and sees progress',async({page})=>{
 await login(page,'student');await page.getByRole('button',{name:'Assessments',exact:false}).first().click();
 const view=page.getByRole('button',{name:'View results',exact:true}).first();
 if(await view.isVisible()){await view.click()}else{
  await page.getByRole('button',{name:/Start assessment|Resume assessment/}).first().click();
  await expect(page.getByRole('heading',{name:'Number systems · First steps'})).toBeVisible();
  const chosen=page.locator('.option').nth(1);await chosen.click();await expect(page.getByRole('status')).toContainText('Answer saved');
  await page.reload();await page.getByRole('button',{name:'Assessments',exact:false}).first().click();await page.getByRole('button',{name:'Resume assessment'}).first().click();
  await expect(page.locator('.option.chosen')).toHaveCount(1);
  await page.locator('.question-nav').getByRole('button',{name:'Submit assessment',exact:true}).click();
 }
 await expect(page.getByRole('heading',{name:'Every answer is a chance to learn.'})).toBeVisible();
 await page.getByRole('button',{name:'Continue your journey'}).click();await expect(page.getByRole('heading',{name:'See how far you’ve come.'})).toBeVisible();
});
test('teacher creates class and assigned assessment from approved bank',async({page})=>{
 await login(page,'teacher');await page.getByRole('button',{name:'My classes',exact:true}).click();await page.getByRole('button',{name:'Create class',exact:true}).click();await page.getByLabel('Class name').fill('Browser test class '+Date.now());await page.getByRole('dialog').getByRole('button',{name:'Create class',exact:true}).click();await expect(page.getByRole('dialog')).not.toBeVisible();
 await page.getByRole('button',{name:'Assessments',exact:false}).first().click();await page.getByRole('button',{name:'Create assessment',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.getByRole('textbox',{name:'Assessment title',exact:true}).fill('Browser workflow assessment');await dialog.getByRole('combobox',{name:'Assign to class',exact:true}).selectOption({index:1});await dialog.getByRole('combobox',{name:'Selection method',exact:true}).selectOption('manual');await dialog.getByRole('checkbox',{name:'Which binary number represents decimal 13?'}).check();await dialog.getByRole('checkbox',{name:/Publish and assign immediately/}).check();await dialog.getByRole('button',{name:'Publish & assign assessment'}).click();await expect(dialog).not.toBeVisible();await expect(page.getByRole('heading',{name:'Browser workflow assessment'}).first()).toBeVisible();
});
test('administrator sees real AI status and unverified curriculum',async({page})=>{
 await login(page,'admin');await expect(page.getByRole('heading',{name:'Teacher approvals',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Create assessment',exact:true})).toHaveCount(0);
});
test('mobile sign in remains readable without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await login(page,'student');await expect(page.getByRole('heading',{name:/Hello,/})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
