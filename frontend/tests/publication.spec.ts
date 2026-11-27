import {test,expect,Page} from '@playwright/test';
async function workspace(page:Page){
 const writes:{path:string;body:any}[]=[];let published=false;
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;let data:unknown=[];
  if(route.request().method()==='POST'){writes.push({path,body:route.request().postDataJSON()});if(path.endsWith('/publish'))published=true;data={id:88};}
  else if(path==='/api/me')data={id:2,name:'Teacher',role:'teacher',email:'teacher@example.invalid',grade:12,language:'en'};
  else if(path==='/api/classes')data=[{id:7,name:'Fixture class',grade:12,members:0}];
  else if(path==='/api/assessments')data=[{id:11,title:'Saved draft',published,class_id:7,questions:1,duration:15}];
  else if(path==='/api/curriculum')data={units:[{id:3,name:'Data Representation',outcomes:[{id:'verified',level:'3.1',text:'Converts numbers between bases',verified:true}]}]};
  else if(path==='/api/coverage')data={outcomes:[]};
  else if(path==='/api/questions')data=[{id:77,status:'approved',outcome_id:'verified',kind:'mcq',difficulty:'easy',prompt:'Which binary number represents decimal thirteen?',options:['1100','1101','1110','1111'].map((text,index)=>({id:'ABCD'[index],text})),key:{answer:'B'},explanation:'Eight plus four plus one equals thirteen.',sources:[],rubric:[]}];
  await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });await page.goto('/');return writes;
}
test('saved assessment drafts can be published without creating another assessment',async({page})=>{
 const writes=await workspace(page);
 await page.getByRole('button',{name:'Assessments',exact:false}).first().click();
 await page.getByRole('button',{name:'Publish assessment',exact:true}).click();
 await expect(page.getByRole('button',{name:'Publish assessment',exact:true})).toHaveCount(0);
 expect(writes.map(row=>row.path)).toEqual(['/api/assessments/11/publish']);
});
test('editing an approved question creates a new draft and preserves the approved record',async({page})=>{
 const writes=await workspace(page);
 await page.getByRole('button',{name:'Question bank',exact:true}).click();
 await page.locator('.question-detail > summary').click();
 await page.getByRole('button',{name:'Edit as new draft',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'Validate & save draft',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 expect(writes).toHaveLength(1);expect(writes[0].path).toBe('/api/questions');
 expect(writes[0].body).not.toHaveProperty('id');expect(writes[0].body).not.toHaveProperty('status');
});
