import {expect, Page, test} from '@playwright/test';

const official = {id:'NIE2017-10.1-01',level:'10.1',subtopic:'Explores the need for web',text:'Describes www',source_page:52,source_pages:[52],verified:true,catalogued:true,reviewed_at:'2026-11-22'};
const pending = {id:'pending',level:'10.1',subtopic:'Explores the need for web',text:'Unreviewed fixture outcome',source_page:52,verified:false,catalogued:true};
const authored = {id:'authored-demo',level:'10.1',subtopic:'Explores the need for web',text:'Additional authored fixture outcome',source_page:52,verified:true,catalogued:false};
const questionBank = [
  {id:11,outcome_id:official.id,prompt:'Which description identifies the world wide web?',kind:'mcq',difficulty:'easy',status:'approved',options:[],key:{answer:'ANSWER_KEY_SENTINEL'},explanation:'PRIVATE_EXPLANATION_SENTINEL'},
  {id:12,outcome_id:official.id,prompt:'Explain the purpose of a web portal.',kind:'structured',difficulty:'medium',status:'approved',options:[],key:{answer:'ANSWER_KEY_SENTINEL'},explanation:'PRIVATE_EXPLANATION_SENTINEL'},
  {id:13,outcome_id:official.id,prompt:'Which example is a web portal?',kind:'mcq',difficulty:'medium',status:'approved',options:[],key:{answer:'ANSWER_KEY_SENTINEL'},explanation:'PRIVATE_EXPLANATION_SENTINEL'},
  {id:14,outcome_id:pending.id,prompt:'This question belongs to an unverified outcome.',kind:'mcq',difficulty:'easy',status:'approved',options:[],key:{answer:'ANSWER_KEY_SENTINEL'},explanation:'PRIVATE_EXPLANATION_SENTINEL'},
];

async function workspace(page: Page, shortage = false) {
  const requests: {path:string;body:any}[] = [];
  await page.route('**/api/**', async route => {
    const request=route.request();
    const path=new URL(request.url()).pathname;
    let status=200;
    let data:unknown=[];
    if (path==='/api/me') data={id:2,name:'Fixture Teacher',email:'fixture@example.invalid',role:'teacher',grade:12,language:'en'};
    else if (path==='/api/classes') data=[{id:7,name:'ICT fixture class',grade:12,code:'FIXTURE',members:1}];
    else if (path==='/api/questions' && request.method()==='GET') data=questionBank;
    else if (path==='/api/questions' && request.method()==='POST') {requests.push({path,body:request.postDataJSON()});data={id:91,status:'draft'};}
    else if (path==='/api/curriculum') data={
      inventory:{unit_count:2,level_count:3,outcome_count:2,verified_outcome_count:1,complete:false,exam_applicability_verified:false},
      units:[
        {id:10,name:'Web Development',grade:null,verified:true,outcomes:[official,pending,authored],levels:[{id:'level-10-1',level:'10.1',title:'Explores the need for web',contents:['The world wide web (www)','Web portals'],source_pages:[52],periods:8,source_verified:true}]},
        {id:14,name:'Project',grade:13,verified:true,outcomes:[],levels:[{id:'level-14-1',level:'14.1',title:'Conducts a project on designing an information system',contents:[],source_pages:[60,61],periods:null,source_verified:true},{id:'level-14-2',level:'14.2',title:'Implements and demonstrates the Information system',contents:[],source_pages:[61],periods:null,source_verified:true}]},
      ],
    };
    else if (path==='/api/coverage') data={covered_outcomes:1,imported_outcomes:3,outcomes:[{id:official.id,approved_questions:3,covered:false,sinhala:false},{id:authored.id,approved_questions:1,covered:true,sinhala:false}]};
    else if (path==='/api/assessments/preview') {
      const body=request.postDataJSON();requests.push({path,body});
      if (shortage) {status=422;data={detail:{message:'Only 1 matching approved question is available; 3 were requested.',requested_count:3,available_count:1,shortage:2}};}
      else data={question_ids:[11,13],questions:questionBank.filter(question=>[11,13].includes(question.id)).map(({id,outcome_id,prompt,kind,difficulty})=>({id,outcome_id,prompt,kind,difficulty,unit_id:10,outcome:'Describes www'})),requested_count:2,available_count:2,count:2,shortage:0,style:body.style,practice_notice:'Practice format only; not an official examination replica.',coverage:{requested_outcome_count:1,represented_outcome_count:1,outcome_ids:[official.id],per_outcome:[{outcome_id:official.id,available:2,selected:2}]}};
    } else if (path==='/api/assessments' && request.method()==='POST') {requests.push({path,body:request.postDataJSON()});data={id:90};}
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('/');
  await expect(page.locator('.main-shell')).toBeVisible();
  return requests;
}

async function assessmentDialog(page:Page) {
  await page.locator('nav').getByRole('button',{name:/^Assessments/}).click();
  await page.getByRole('button',{name:'Create assessment',exact:true}).click();
  return page.getByRole('dialog');
}

test('curriculum searches source topics and keeps project competencies without invented outcomes',async({page})=>{
  await workspace(page);
  await page.getByRole('button',{name:'Curriculum',exact:true}).click();
  await expect(page.getByText('Current examination applicability still requires official confirmation.',{exact:false})).toBeVisible();
  await page.getByRole('searchbox',{name:'Search units, topics or outcomes',exact:true}).fill('web portals');
  await expect(page.getByText('Describes www',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Open source PDF page 52'}).first()).toHaveAttribute('href','/api/curriculum/source#page=52');
  await page.getByRole('searchbox',{name:'Search units, topics or outcomes',exact:true}).fill('');
  await page.getByRole('combobox',{name:'Unit',exact:true}).selectOption('14');
  await expect(page.getByText('No explicit outcome bullets in the source').first()).toBeVisible();
  await expect(page.getByText(/without inventing outcomes/).first()).toBeVisible();
  await expect(page.getByRole('heading',{name:'Conducts a project on designing an information system',exact:true})).toBeVisible();
  await expect(page.getByText(/Grade 13/).first()).toBeVisible();
});

test('balanced preview respects paper style and saves only selected IDs as an unpublished draft',async({page})=>{
  const requests=await workspace(page);
  const dialog=await assessmentDialog(page);
  await dialog.getByRole('textbox',{name:'Assessment title',exact:true}).fill('Web practice fixture');
  await dialog.getByRole('combobox',{name:'Assign to class',exact:true}).selectOption('7');
  await dialog.getByRole('combobox',{name:'Practice format',exact:true}).selectOption('paper_i');
  await dialog.getByRole('spinbutton',{name:'Number of questions',exact:true}).fill('2');
  await dialog.getByRole('button',{name:'Preview balanced selection',exact:true}).click();
  await expect(dialog.getByRole('region',{name:'Assessment preview'})).toContainText('2 questions across 1 learning outcome');
  await expect(dialog).not.toContainText('ANSWER_KEY_SENTINEL');
  await expect(dialog).not.toContainText('PRIVATE_EXPLANATION_SENTINEL');
  expect(requests.find(request=>request.path.endsWith('/preview'))?.body).toEqual({outcome_ids:[],unit_ids:[],difficulty:null,kinds:['mcq'],count:2,style:'paper_i'});
  await dialog.getByRole('button',{name:'Save draft assessment',exact:true}).click();
  await expect(dialog).toBeHidden();
  expect(requests.find(request=>request.path==='/api/assessments')?.body).toEqual({title:'Web practice fixture',class_id:7,duration:60,question_ids:[11,13],published:false});
});

test('a question shortage remains visible and cannot create an assessment',async({page})=>{
  const requests=await workspace(page,true);
  const dialog=await assessmentDialog(page);
  await dialog.getByRole('spinbutton',{name:'Number of questions',exact:true}).fill('3');
  await dialog.getByRole('button',{name:'Preview balanced selection',exact:true}).click();
  await expect(dialog.getByRole('alert')).toContainText('Only 1 matching approved question is available; 3 were requested.');
  await expect(dialog.getByRole('button',{name:'Save draft assessment',exact:true})).toBeDisabled();
  expect(requests.filter(request=>request.path==='/api/assessments')).toHaveLength(0);
});

test('manual selection excludes approved questions whose learning outcome is unverified',async({page})=>{
  await workspace(page);
  const dialog=await assessmentDialog(page);
  await dialog.getByRole('combobox',{name:'Selection method',exact:true}).selectOption('manual');
  const picker=dialog.locator('.builder-question-picker');
  await expect(dialog.getByText('Which description identifies the world wide web?',{exact:true})).toBeVisible();
  await expect(dialog.getByText('This question belongs to an unverified outcome.',{exact:true})).toHaveCount(0);
  await expect(dialog).not.toContainText('ANSWER_KEY_SENTINEL');
  await dialog.getByRole('checkbox',{name:/Which description identifies the world wide web/}).check();
  await expect(dialog.getByRole('status')).toContainText('1 question selected across 1 learning outcome');
  await expect(picker).toBeVisible();
});

test('the question editor saves a five-option draft with an explicit correct option',async({page})=>{
  const requests=await workspace(page);
  await page.getByRole('button',{name:'Question bank',exact:true}).click();
  await page.getByRole('button',{name:'Manual draft',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByRole('combobox',{name:'Learning outcome',exact:true}).selectOption(official.id);
  await dialog.getByRole('textbox',{name:'Question prompt',exact:true}).fill('Which service is a web portal?');
  await dialog.getByRole('combobox',{name:'Number of options',exact:true}).selectOption('5');
  for (const [id,text] of [['A','A storage device'],['B','A collection of online services'],['C','A network cable'],['D','An operating system'],['E','A logic circuit']]) await dialog.getByRole('textbox',{name:`Option ${id}`,exact:true}).fill(text);
  await dialog.getByRole('combobox',{name:'Correct answer',exact:true}).selectOption('B');
  await dialog.getByRole('textbox',{name:'Worked explanation',exact:true}).fill('A web portal provides access to a collection of information and online services.');
  await dialog.getByRole('button',{name:'Validate & save draft',exact:true}).click();
  await expect(dialog).toBeHidden();
  const payload=requests.find(request=>request.path==='/api/questions')?.body;
  expect(payload.options).toHaveLength(5);
  expect(payload.key).toEqual({answer:'B'});
  expect(payload.outcome_id).toBe(official.id);
  expect(payload).not.toHaveProperty('status');
});

test('descriptive question drafts preserve separate marking criteria and expected elements',async({page})=>{
  const requests=await workspace(page);
  await page.getByRole('button',{name:'Question bank',exact:true}).click();
  await page.getByRole('button',{name:'Manual draft',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByRole('combobox',{name:'Learning outcome',exact:true}).selectOption(official.id);
  await dialog.getByRole('combobox',{name:'Question format',exact:true}).selectOption('structured');
  await dialog.getByRole('textbox',{name:'Question prompt',exact:true}).fill('Describe a web portal and give an example of a useful service.');
  await dialog.getByRole('textbox',{name:'Criterion 1',exact:true}).fill('Explains the purpose of a web portal');
  await dialog.getByRole('spinbutton',{name:'Marks for criterion 1',exact:true}).fill('2');
  await dialog.getByRole('textbox',{name:'Expected elements for criterion 1 (optional)',exact:true}).fill('Collection of online information\nAccess to services');
  await dialog.getByRole('button',{name:'Add criterion',exact:true}).click();
  await dialog.getByRole('textbox',{name:'Criterion 2',exact:true}).fill('Gives a relevant service example');
  await dialog.getByRole('textbox',{name:'Part for criterion 2 (optional)',exact:true}).fill('(b)');
  await dialog.getByRole('textbox',{name:'Worked explanation',exact:true}).fill('A portal collects access to information and services, such as school learning resources.');
  await dialog.getByRole('button',{name:'Validate & save draft',exact:true}).click();
  await expect(dialog).toBeHidden();
  const payload=requests.find(request=>request.path==='/api/questions')?.body;
  expect(payload.kind).toBe('structured');
  expect(payload.options).toEqual([]);
  expect(payload.rubric).toEqual([{criterion:'Explains the purpose of a web portal',marks:2,expected_elements:['Collection of online information','Access to services']},{criterion:'Gives a relevant service example',marks:1,expected_elements:[],part:'(b)'}]);
  expect(payload).not.toHaveProperty('status');
});
