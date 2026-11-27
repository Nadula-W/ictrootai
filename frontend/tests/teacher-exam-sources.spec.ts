import {test,expect,Page} from '@playwright/test';
async function workspace(page:Page,role='teacher',ready=true){
 const writes:any[]=[];let generated=false;
 const q={id:1,outcome_id:'verified',kind:'mcq',difficulty:'medium',prompt:'Approved bank question?',status:'approved',options:[],key:{answer:'A'},sources:[1],explanation:'Checked explanation.',rubric:[]};
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;let data:any=[];
  if(path==='/api/me')data={id:2,name:'Teacher',email:'teacher@example.invalid',role,grade:12,language:'en'};
  else if(path==='/api/classes')data=[{id:7,name:'ICT class',grade:12,members:0}];
  else if(path==='/api/curriculum')data={units:[{id:3,name:'Data Representation',outcomes:[{id:'verified',level:'3.1',text:'Verified conversion outcome',verified:true}]}]};
  else if(path==='/api/coverage')data={outcomes:[]};
  else if(path==='/api/questions')data=generated?[q,{...q,id:2,status:'draft',prompt:'AI generated question?'}]:[q];
  else if(path==='/api/ai/readiness')data={ready,message:'Reviewed notes must be indexed first.'};
  else if(path==='/api/admin/teacher-applications')data=[{id:3,name:'New teacher',email:'new@example.invalid',message:'School details',status:'pending'}];
  if(route.request().method()==='POST'){
   writes.push({path,body:route.request().postData()?route.request().postDataJSON():null});data={id:9};
   if(path==='/api/ai/generate'){generated=true;data={id:2,status:'draft'}}
   if(path==='/api/assessments/preview')data={question_ids:[1],questions:[q],available_count:1};
  }
  await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });await page.goto('/');return writes;
}
for(const source of ['Generate with AI','Mix bank + AI'])test(`${source} requires teacher review and saves exactly the chosen sources`,async({page})=>{
 const writes=await workspace(page);await page.getByRole('button',{name:/^Assessments/}).first().click();await page.getByRole('button',{name:'Create assessment',exact:true}).click();
 const dialog=page.getByRole('dialog');await dialog.getByRole('radio',{name:source,exact:true}).check();
 await dialog.getByRole('textbox',{name:'Assessment title',exact:true}).fill('AI exam');await dialog.getByRole('combobox',{name:'Assign to class',exact:true}).selectOption('7');
 await dialog.getByRole('spinbutton',{name:'Number of questions',exact:true}).fill(source==='Generate with AI'?'1':'2');
 if(source==='Mix bank + AI')await dialog.getByRole('spinbutton',{name:'AI questions in this exam',exact:true}).fill('1');
 await dialog.locator('summary').filter({hasText:'Filter by learning outcomes'}).click();await dialog.getByRole('checkbox',{name:/Verified conversion outcome/}).check();
 if(source==='Mix bank + AI')await dialog.getByRole('button',{name:'Preview balanced selection',exact:true}).click();
 await dialog.getByRole('button',{name:'Generate AI questions',exact:true}).click();
 await dialog.getByText('Needs your review · AI generated question?',{exact:true}).click();
 await expect(dialog.getByRole('button',{name:'Save draft assessment',exact:true})).toBeDisabled();
 await dialog.getByRole('textbox',{name:'Review reason',exact:true}).fill('Answer and original sources checked');await dialog.getByRole('checkbox',{name:'I checked the answer, explanation and sources',exact:true}).check();await dialog.getByRole('button',{name:'Approve for this exam',exact:true}).click();
 await dialog.getByRole('button',{name:'Save draft assessment',exact:true}).click();await expect(dialog).toHaveCount(0);
 expect(writes.find(w=>w.path==='/api/assessments').body.question_ids).toEqual(source==='Generate with AI'?[2]:[1,2]);
});
test('administrator sees teacher approvals while approved teachers have resource tools',async({page})=>{
 await workspace(page,'admin');await expect(page.getByRole('heading',{name:'Teacher approvals',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Teaching resources',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Accept teacher',exact:true})).toBeDisabled();
 await page.getByRole('textbox',{name:'Decision reason',exact:true}).fill('School credentials checked');await page.getByRole('button',{name:'Accept teacher',exact:true}).click();
});
