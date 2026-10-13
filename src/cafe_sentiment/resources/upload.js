"use strict";
const byId = id => document.getElementById(id);
let selectedFile = null, jobId = null, revision = 0, busy = false;
const issueNames = {blank_rows:"빈 기록 제외",missing_required:"본문·필수 정보 누락 제외",duplicate_id:"중복 리뷰 ID 제외",missing_date:"작성일 없음",invalid_date:"작성일 형식 또는 날짜 확인 필요"};

function message(text, loading=false) { byId("status").textContent=text; byId("status").classList.toggle("busy",loading); }
function error(text) { byId("error").textContent=text; byId("error").hidden=!text; }
function lock(value) {
  busy=value;
  for(const id of ["csv-file","cafe-name","source","sample-load","preview-btn","analyze-btn","period","start-date","end-date"]) byId(id).disabled=value;
  if(!value){byId("preview-btn").disabled=!selectedFile;byId("analyze-btn").disabled=!jobId;}
}
function step(number) { ["step-file","step-check","step-report"].forEach((id,i)=>{byId(id).classList.toggle("current",i===number-1);byId(id).classList.toggle("done",i<number-1);}); }
function invalidate() {
  revision++; jobId=null; error(""); message(""); step(1);
  byId("welcome-panel").hidden=false;byId("preview-panel").hidden=true;byId("result-panel").hidden=true;
  byId("preview-btn").disabled=!selectedFile;byId("analyze-btn").disabled=true;
}
function setFile(file) {
  if(busy)return;
  selectedFile=file;invalidate();
  if(!file){byId("csv-file").value="";byId("file-label").textContent="리뷰 CSV를 여기에 놓으세요";return;}
  if(byId("csv-file").files[0]!==file){const transfer=new DataTransfer();transfer.items.add(file);byId("csv-file").files=transfer.files;}
  byId("file-label").textContent=file.name;
  if(file.size>10*1024*1024){error("CSV는 10MB 이하로 준비해주세요.");selectedFile=null;byId("preview-btn").disabled=true;}
  else if(!file.name.toLowerCase().endsWith(".csv")){error("CSV 파일을 선택해주세요. Excel 파일은 CSV UTF-8로 저장하세요.");selectedFile=null;byId("preview-btn").disabled=true;}
}
async function api(url, payload) {
  let response;
  try{response=await fetch(url,payload===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});}catch{throw new Error("로컬 서버에 연결하지 못했습니다. 서버를 실행한 뒤 다시 확인해주세요.");}
  let result;
  try{result=await response.json();}catch{throw new Error("서버 응답을 읽지 못했습니다. 로컬 서버가 실행 중인지 확인해주세요.");}
  if(!response.ok)throw new Error(result.error||"요청을 처리하지 못했습니다.");
  return result;
}
function renderPreview(job) {
  const p=job.preview,c=p.counts;
  byId("file-summary").textContent=`${job.filename} · ${p.format==="crawler_csv"?"크롤러 / 분석용 CSV":"본문·작성일 두 열 CSV"} · ${p.sources.join(", ")}`;
  byId("stats").replaceChildren();
  [["전체 기록",c.input_rows],["사용 가능",c.accepted_rows],["작성일 확인",c.dated_rows||0],["제외한 기록",c.excluded_rows||0],["작성일 미상",c.unknown_dates||0],["카페 수",c.cafe_count]].forEach(([label,value])=>{
    const box=document.createElement("div"),name=document.createElement("span"),number=document.createElement("strong");box.className="stat";name.textContent=label;number.textContent=value.toLocaleString("ko-KR");box.append(name,number);byId("stats").append(box);
  });
  byId("date-range").textContent=p.date_start?`작성일 범위 ${p.date_start} ~ ${p.date_end} · ${p.month_count}개 월에 리뷰가 있습니다.`:"확인된 작성일이 없습니다. 기간 합산을 볼 수 있지만 월별 추세는 만들 수 없습니다.";
  const warnings=[];
  if(c.excluded_rows)warnings.push(`${c.excluded_rows}개 기록은 빈 본문·필수 정보 누락·중복 등으로 제외했습니다.`);
  if(c.unknown_dates)warnings.push(`${c.unknown_dates}개 리뷰는 작성일 미상입니다. 날짜를 지정하지 않은 전체 기간 집계에는 포함하고, 월별 집계에서는 제외합니다.`);
  if(p.ignored_columns.length)warnings.push("분석에 사용하지 않는 추가 열은 저장하지 않았습니다.");
  byId("warnings").replaceChildren();warnings.forEach(text=>{const p=document.createElement("p");p.textContent=text;byId("warnings").append(p);});byId("warnings").hidden=!warnings.length;
  byId("visit-note").hidden=!c.visit_only;byId("visit-note").textContent=c.visit_only?`${c.visit_only}개 리뷰는 방문일만 확인됩니다. 방문일을 작성일로 바꾸지 않으므로 월별 집계에 포함되지 않습니다.`:"";
  byId("preview-body").replaceChildren();
  p.rows.forEach(row=>{const tr=document.createElement("tr");[row.cafe_name||"이름 미기록",row.review_date||"작성일 미상",row.text].forEach((value,i)=>{const td=document.createElement("td");if(i===2){const body=document.createElement("div");body.className="body-preview";body.textContent=value;td.append(body);}else td.textContent=value;tr.append(td);});byId("preview-body").append(tr);});
  byId("issue-list").replaceChildren();p.issue_examples.forEach(item=>{const li=document.createElement("li");li.textContent=`${item.record_number}번째 기록 · ${issueNames[item.issue]||item.issue}`;byId("issue-list").append(li);});
  byId("issue-details").hidden=!p.issue_examples.length;
  byId("welcome-panel").hidden=true;byId("preview-panel").hidden=false;byId("result-panel").hidden=true;step(2);
}
byId("csv-file").addEventListener("change",event=>setFile(event.target.files[0]||null));
for(const id of ["cafe-name","source"])byId(id).addEventListener("input",()=>{if(!busy)invalidate();});
byId("drop-zone").addEventListener("dragover",event=>{event.preventDefault();if(!busy)byId("drop-zone").classList.add("drag-over");});
byId("drop-zone").addEventListener("dragleave",()=>byId("drop-zone").classList.remove("drag-over"));
byId("drop-zone").addEventListener("drop",event=>{event.preventDefault();byId("drop-zone").classList.remove("drag-over");if(!busy)setFile(event.dataTransfer.files[0]||null);});
byId("sample-load").addEventListener("click",async()=>{
  if(busy)return;error("");message("자체 작성 예제 CSV를 준비 중입니다.",true);lock(true);
  try{const response=await fetch("/api/sample");if(!response.ok)throw new Error("예제 파일을 읽지 못했습니다.");const file=new File([await response.blob()],"카페리뷰_자체작성예제.synthetic.csv",{type:"text/csv"});lock(false);byId("csv-file").value="";byId("cafe-name").value="";byId("source").value="synthetic";setFile(file);message("자체 작성 예제 250건을 선택했습니다. 입력 확인하기를 눌러주세요.");}
  catch(e){lock(false);message("");error(e.message);}
});
byId("preview-btn").addEventListener("click",async()=>{
  if(!selectedFile||busy)return;const current=revision;error("");message("CSV의 본문·날짜·중복을 확인 중입니다.",true);lock(true);
  try{let text;try{text=new TextDecoder("utf-8",{fatal:true}).decode(await selectedFile.arrayBuffer());}catch{throw new Error("UTF-8 CSV로 다시 저장해주세요. Excel에서는 CSV UTF-8을 선택합니다.");}
    const job=await api("/api/preview",{csv:text,cafe_name:byId("cafe-name").value,source:byId("source").value,filename:selectedFile.name});
    if(current!==revision)return;jobId=job.id;renderPreview(job);message("입력 확인을 마쳤습니다. 분석할 기간을 선택하거나 그대로 보고서를 만드세요.");
  }catch(e){jobId=null;message("");error(e.message);}finally{lock(false);}
});
byId("analyze-btn").addEventListener("click",async()=>{
  if(!jobId||busy)return;error("");message("감성분석과 보고서를 생성 중입니다. 리뷰 수에 따라 시간이 걸립니다.",true);lock(true);
  try{
    let job=await api(`/api/jobs/${jobId}/analyze`,{period:byId("period").value,start:byId("start-date").value,end:byId("end-date").value});
    while(job.status==="running"){await new Promise(resolve=>setTimeout(resolve,600));job=await api(`/api/jobs/${jobId}`);}
    if(job.status!=="complete")throw new Error(job.error||"분석을 마치지 못했습니다. 입력 확인을 다시 눌러주세요.");
    byId("result-summary").textContent=`전체 입력 ${job.analysis_counts.analyzed_rows.toLocaleString("ko-KR")}건을 분석했습니다. 보고서의 선택 기간 집계에는 ${job.included_rows.toLocaleString("ko-KR")}건이 포함됩니다.`;
    const links={"open-report":job.report_url,"download-report":job.downloads["report.html"],"download-summary":job.downloads["summary.csv"],"download-input":job.normalized_csv,"download-issues":job.upload_issues,"download-detail":job.downloads["reviews.jsonl"],"download-metadata":job.downloads["run_metadata.json"],"download-analysis-issues":job.downloads["input_issues.csv"]};
    Object.entries(links).forEach(([id,url])=>{byId(id).href=url;});byId("result-panel").hidden=false;step(3);message("분석이 완료됐습니다. 보고서 열기에서 점수와 월별 변화를 확인하세요.");byId("result-panel").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(e){message("");error(e.message);}finally{lock(false);}
});
byId("reset-btn").addEventListener("click",()=>{byId("csv-file").value="";byId("cafe-name").value="";byId("source").value="naver_place";byId("start-date").value="";byId("end-date").value="";byId("period").value="month";setFile(null);byId("drop-zone").scrollIntoView({behavior:"smooth",block:"center"});});
for(const id of ["period","start-date","end-date"])byId(id).addEventListener("input",()=>{
  if(!busy&&!byId("result-panel").hidden){jobId=null;byId("result-panel").hidden=true;byId("analyze-btn").disabled=true;step(2);message("기간 설정이 바뀌었습니다. 입력 확인하기를 다시 누른 뒤 새 보고서를 만드세요.");}
});
api("/api/health").then(value=>{byId("demo-link").hidden=!value.demo_available;}).catch(()=>error("로컬 서버 연결을 확인해주세요."));
