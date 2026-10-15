const $ = id => document.getElementById(id);
const state = {csvText:'',columns:[],results:null,charts:[]};
const status = text => {$('status').textContent=text;};
let api = localStorage.getItem('regression-api') || (location.hostname==='localhost'||location.hostname==='127.0.0.1'?'http://127.0.0.1:8001':'');
$('api').value=api;
$('api').addEventListener('change',()=>{api=$('api').value.trim().replace(/\/$/,'');localStorage.setItem('regression-api',api);});
async function request(path, opts){
 const base=$('api').value.trim().replace(/\/$/,'');
 if(!base)throw Error('請先輸入 FastAPI URL（例如 https://your-service.onrender.com）');
 const res=await fetch(base+path,opts);const body=await res.json().catch(()=>({detail:'Invalid server response'}));
 if(!res.ok)throw Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));return body;
}
function cell(s){const e=document.createElement('td');e.textContent=s==null?'':String(s);return e;}
function addRow(table,values,tag='tr'){const tr=document.createElement(tag);values.forEach(v=>tr.appendChild(cell(v)));table.appendChild(tr);}
function loaded(data){state.csvText=data.csv_text;state.columns=data.columns;status(`已載入 ${data.rows} 筆、${data.columns.length} 欄。請選 Target 與 Features。`);
 $('preview').innerHTML='';const t=document.createElement('table');const th=document.createElement('thead');addRow(th,data.columns);t.appendChild(th);const tbody=document.createElement('tbody');data.preview.forEach(row=>addRow(tbody,data.columns.map(c=>row[c])));t.appendChild(tbody);$('preview').appendChild(t);
 $('target').innerHTML='';const nums=data.numeric_columns;nums.forEach(name=>{const o=new Option(name,name);$('target').add(o);});$('target').value=nums.includes('Profit')?'Profit':nums[nums.length-1]||'';
 renderFeatures();$('target').onchange=renderFeatures;
}
function renderFeatures(){const selected=$('target').value;$('features').innerHTML='';state.columns.filter(c=>c!==selected).forEach(c=>{const label=document.createElement('label');const inp=document.createElement('input');inp.type='checkbox';inp.value=c;inp.checked=true;label.append(inp,document.createTextNode(c));$('features').appendChild(label);});}
$('loadUrl').onclick=async()=>{try{status('正在下載 CSV...');const data=await request('/api/dataset/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('url').value.trim()})});loaded(data);}catch(e){status('錯誤：'+e.message);}};
$('file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{status('正在讀取 CSV...');const form=new FormData();form.append('file',file);loaded(await request('/api/dataset/upload',{method:'POST',body:form}));}catch(e){status('錯誤：'+e.message);}};
$('train').onclick=async()=>{try{if(!state.csvText)throw Error('請先匯入 Dataset');const features=[...$('features').querySelectorAll('input:checked')].map(x=>x.value);if(features.length===0)throw Error('至少選一個 Feature');status('模型訓練中（特徵多時可能需數十秒）...');$('train').disabled=true;const data=await request('/api/train',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:state.csvText,target:$('target').value,features,max_features:Number($('maxf').value),test_size:Number($('split').value)})});state.results=data;renderResults(data);status('完成：'+data.dataset.total_experiments+' 組模型與特徵組合');$('charts').scrollIntoView({behavior:'smooth'});}catch(e){status('錯誤：'+e.message);}finally{$('train').disabled=false;}};
const palette=['#2563eb','#e87932','#22a06b','#d53a71','#885ac0'];
function chart(id,metric,title){const rows=state.results.best_per_count;const methods=[...new Set(rows.map(r=>r.method))];const sets=methods.map((name,i)=>({label:name,data:rows.filter(r=>r.method===name).sort((a,b)=>a.number_of_features-b.number_of_features).map(r=>({x:r.number_of_features,y:r[metric]})),borderColor:palette[i],backgroundColor:palette[i],pointRadius:4,tension:0.05}));const c=new Chart($(id),{type:'line',data:{datasets:sets},options:{responsive:true,maintainAspectRatio:false,plugins:{title:{display:true,text:title},legend:{position:'bottom'}},scales:{x:{type:'linear',min:1,max:Math.max(...rows.map(r=>r.number_of_features)),ticks:{stepSize:1},title:{display:true,text:'Number of Features'}},y:{title:{display:true,text:metric==='rmse'?'RMSE (Lower is Better)':'R-squared (Higher is Better)'}}}}});state.charts.push(c);}
function renderResults(data){$('charts').hidden=false;state.charts.forEach(x=>x.destroy());state.charts=[];const b=data.best_overall;$('stats').innerHTML='';[['Best Method',b.method],['Best Feature Count',b.number_of_features],['CV RMSE',b.cv_rmse]].forEach(([label,value])=>{const d=document.createElement('div');d.className='stat';const s=document.createElement('strong');s.textContent=value;const t=document.createElement('span');t.textContent=label;d.append(s,t);$('stats').appendChild(d);});chart('rmse','rmse','RMSE Comparison across Five Regression Methods');chart('r2','r2','R-squared Comparison across Five Regression Methods');const methods=[...new Set(data.best_per_count.map(r=>r.method))];$('method').innerHTML='';methods.forEach(m=>$('method').add(new Option(m,m)));$('method').onchange=()=>renderTable(data.best_per_count,$('method').value);renderTable(data.best_per_count,methods[0]);}
function renderTable(rows,method){$('results').innerHTML='';rows.filter(r=>r.method===method).sort((a,b)=>a.number_of_features-b.number_of_features).forEach(r=>addRow($('results'),[r.number_of_features,r.features.join(', '),JSON.stringify(r.parameters),r.cv_rmse,r.rmse,r.r2,r.mae]));}
function download(name,blob){const a=document.createElement('a');const u=URL.createObjectURL(blob);a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function csv(rows){if(!rows.length)return '';const keys=Object.keys(rows[0]);const esc=v=>'"'+(typeof v==='object'?JSON.stringify(v):String(v??'')).replace(/"/g,'""')+'"';return [keys.map(esc).join(','),...rows.map(r=>keys.map(k=>esc(r[k])).join(','))].join('\r\n');}
$('saveBest').onclick=()=>download('best_per_count.csv',new Blob(['\ufeff'+csv(state.results.best_per_count)],{type:'text/csv'}));
$('saveAll').onclick=()=>download('all_subsets.csv',new Blob(['\ufeff'+csv(state.results.all_subsets)],{type:'text/csv'}));
$('savePred').onclick=()=>download('predictions.csv',new Blob(['\ufeff'+csv(state.results.predictions)],{type:'text/csv'}));
$('saveJson').onclick=()=>download('regression_results.json',new Blob([JSON.stringify(state.results,null,2)],{type:'application/json'}));
