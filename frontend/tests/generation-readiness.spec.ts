import {test,expect,Page} from '@playwright/test';

async function questionBank(page:Page,mode:'missing'|'ready'='missing',rateLimited=false){
 const calls:string[]=[];
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());
  const path=url.pathname;
  let data:unknown=[];
  let status=200;
  const headers:Record<string,string>={};
  if(path==='/api/me')data={id:2,name:'QA Teacher',email:'qa@example.invalid',role:'teacher',grade:12,language:'en'};
  else if(path==='/api/curriculum')data={units:[{id:3,name:'Data Representation',grade:null,outcomes:[{id:'unverified',level:'3.1',text:'Unreviewed outcome',verified:false},{id:'verified',level:'3.1',text:'Verified conversion outcome',verified:true}]}]};
  else if(path==='/api/coverage')data={outcomes:[]};
  else if(path==='/api/ai/readiness'){
   const outcome=url.searchParams.get('outcome_id');
   data=outcome==='unverified'?{outcome_id:outcome,ready:false,code:'outcome_unverified',message:'This syllabus learning outcome has not been checked against its official source.'}:mode==='missing'?{outcome_id:outcome,ready:false,code:'embedding_model_missing',message:"The local search model 'embeddinggemma' is not installed. Install the configured embedding model, then index reviewed learning resources."}:{outcome_id:outcome,ready:true,code:'ready',message:'Local models and reviewed resource index are available.'};
  }else if(path==='/api/ai/generate'){
   calls.push(path);
   status=rateLimited?429:200;
   if(rateLimited){headers['Retry-After']='5';data={detail:'Too many requests. Try again in 5 seconds.'}}
   else data={id:99,status:'draft'};
  }
  await route.fulfill({status,headers,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');
 await page.getByRole('button',{name:'Question bank',exact:true}).click();
 return calls;
}

test('unverified outcome explains source review and disables generation',async({page})=>{
 const calls=await questionBank(page);
 await page.getByLabel('Learning outcome').selectOption('unverified');
 await expect(page.getByRole('status')).toContainText('has not been checked');
 await expect(page.getByRole('button',{name:'Generate local AI draft',exact:true})).toBeDisabled();
 expect(calls).toHaveLength(0);
});

test('missing search model is named before a generation request',async({page})=>{
 const calls=await questionBank(page);
 await page.getByLabel('Learning outcome').selectOption('verified');
 await expect(page.getByRole('status')).toContainText("'embeddinggemma' is not installed");
 await expect(page.getByRole('button',{name:'Generate local AI draft',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Refresh AI status',exact:true}).click();
 await expect(page.getByRole('status')).toContainText("'embeddinggemma' is not installed");
 expect(calls).toHaveLength(0);
});

test('ready setup permits generation and retains teacher-review notice',async({page})=>{
 const calls=await questionBank(page,'ready');
 await page.getByLabel('Learning outcome').selectOption('verified');
 const generate=page.getByRole('button',{name:'Generate local AI draft',exact:true});
 await expect(generate).toBeEnabled();await generate.click();
 await expect(page.getByText('AI draft created. Review its sources, answer and explanation.',{exact:true})).toBeVisible();
 expect(calls).toHaveLength(1);
});

test('rate-limited generation displays and respects retry delay',async({page})=>{
 const calls=await questionBank(page,'ready',true);
 await page.getByLabel('Learning outcome').selectOption('verified');
 await page.getByRole('button',{name:'Generate local AI draft',exact:true}).click();
 await expect(page.locator('.alert[role="alert"]')).toContainText('Try again in 5 seconds');
 await expect(page.getByRole('button',{name:/Try again in \d+s/})).toBeDisabled();
 expect(calls).toHaveLength(1);
});
