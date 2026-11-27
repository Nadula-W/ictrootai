import {test,expect} from '@playwright/test';

test('Sinhala preference changes navigation and titles while source wording stays English',async({page})=>{
 let language='en';
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/me'&&route.request().method()==='PATCH')language=route.request().postDataJSON().language;
  let data:unknown=[];
  if(path==='/api/me')data={id:2,name:'Fixture Teacher',email:'teacher@example.invalid',role:'teacher',grade:12,language};
  if(path==='/api/curriculum')data={units:[{id:3,name:'Data Representation',verified:true,grade:null,outcomes:[{id:'NIE2017-3.1-04',text:'Converts decimal integers into binary',level:'3.1',verified:true,source_page:21,catalogued:true}]}]};
  if(path==='/api/coverage')data={outcomes:[],covered_outcomes:0,imported_outcomes:1,warning:'Examination applicability requires confirmation.'};
  await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');
 await page.getByRole('button',{name:'English',exact:true}).click();
 await page.getByRole('button',{name:'පැතිකඩ',exact:true}).click();
 await expect(page.getByRole('heading',{name:'ඔබට ගැළපෙන ලෙස සකසන්න.'})).toBeVisible();
 await expect(page.locator('html')).toHaveAttribute('lang','si');
 await page.getByRole('button',{name:'විෂය නිර්දේශය',exact:true}).click();
 await page.getByText('Data Representation',{exact:true}).click();
  await page.locator('.syllabus-level > summary').first().click();
 await expect(page.getByText('Converts decimal integers into binary',{exact:true})).toBeVisible();
 await expect(page.getByText('NIE2017-3.1-04',{exact:true})).toBeVisible();
});
