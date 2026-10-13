"use strict";
const DATA=JSON.parse(document.getElementById("annotation-data").textContent);
const $=id=>document.getElementById(id);
const C=AnnotationCore;
const namespace="cafe-annotation:"+DATA.dataset_sha256;
const profileKey=name=>namespace+":profile:"+name;
const add=(parent,tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!=null)node.textContent=text;parent.append(node);return node;};
let reviewer="", decisions=Object.create(null), cursor=DATA.reviews[0].key, selectedQuote="", objectUrl;
const readStorage=key=>{try{return localStorage.getItem(key);}catch{return null;}};
const notice=text=>{$("notice").textContent=text;$("notice").hidden=!text;};
$("reviewer").value=readStorage(namespace+":last-reviewer") || "";
$("dataset-badge").textContent=DATA.is_synthetic?"자체 작성 검토 예제":"실제 리뷰 · 비공개 검토용";
$("dataset-description").textContent=DATA.reviews.length+"개 리뷰 · "+DATA.aspect_count+"개 항목 · 사전 예측과 자동 라벨 없이 시작합니다.";
$("provenance").textContent="검토 화면 "+DATA.ui_version+" · 이 화면은 사람 검토를 돕는 도구이며 검토자 신원을 확인하지 않습니다.";
for(const [id,name] of new Map(DATA.reviews.map(r=>[r.cafe_id,r.cafe_name]))){const option=add($("cafe-filter"),"option",null,name);option.value=id;}

function save(){
  if(!reviewer)return;
  try{
    localStorage.setItem(profileKey(reviewer),JSON.stringify(C.snapshot(DATA,reviewer,decisions,cursor)));
    localStorage.setItem(namespace+":last-reviewer",reviewer);
    $("storage-status").textContent="브라우저에 저장됨 · "+new Date().toLocaleTimeString("ko-KR",{timeZone:"Asia/Seoul",hour:"2-digit",minute:"2-digit"})+" · JSON 저장본으로 다른 기기에서 이어갈 수 있습니다.";
  }catch{$("storage-status").textContent="브라우저 저장을 사용할 수 없습니다. 진행 상황 JSON을 저장해서 입력을 보관해주세요.";}
}
function activate(name,saved){
  reviewer=name;decisions=saved?.decisions || Object.create(null);cursor=saved?.cursor || DATA.reviews[0].key;
  selectedQuote="";
  $("reviewer").value=reviewer;$("active-reviewer").textContent="현재 검토자: "+reviewer;
  $("backup").disabled=$("export").disabled=false;
  $("cafe-filter").value=$("status-filter").value="all";
  save();renderAll();
}
$("start").addEventListener("click",()=>{
  const name=$("reviewer").value.trim();
  if(!name){notice("검토자 이름 또는 별칭을 입력해주세요.");return;}
  try{const stored=readStorage(profileKey(name));activate(name,stored?C.parseSnapshot(DATA,stored):null);notice("");}
  catch(error){notice("저장본을 읽지 못했습니다. 다른 검토자 별칭으로 시작하거나 유효한 JSON 저장본을 불러와주세요. "+error.message);}
});
$("reviewer").addEventListener("input",()=>{
  if(reviewer && $("reviewer").value.trim()!==reviewer) notice("입력은 현재 검토자 ‘"+reviewer+"’로 저장됩니다. 검토자를 바꾸려면 검토 시작 / 이어가기를 누르세요.");
});
function reviewCounts(review){return C.counts([review],decisions);}
function filtered(){return DATA.reviews.filter(r=>{
  if($("cafe-filter").value!=="all" && r.cafe_id!==$("cafe-filter").value)return false;
  const stats=reviewCounts(r),status=$("status-filter").value;
  return status==="all" || status==="remaining" && !stats.finished_reviews || status==="finished" && stats.finished_reviews || status==="deferred" && stats.deferred>0;
});}
function renderProgress(){
  const stats=C.counts(DATA.reviews,decisions);$("progress").replaceChildren();
  for(const [value,label] of [[stats.labeled+" / "+stats.total,"정답 확정 항목"],[stats.deferred,"판단 보류 항목"],[stats.pending+stats.invalid,"미완료 항목"],[stats.finished_reviews+" / "+DATA.reviews.length,"8항목 검토 완료 리뷰"]]){
    const box=add($("progress"),"div","progress-item");add(box,"strong",null,value);add(box,"span",null,label);
  }
  $("progress-fill").style.width=(stats.total?(stats.labeled+stats.deferred)/stats.total*100:0)+"%";
}
function renderList(){
  const list=filtered();$("review-list").replaceChildren();$("list-caption").textContent=list.length+"개 리뷰 표시";
  for(const r of list){
    const stats=reviewCounts(r),index=DATA.reviews.indexOf(r)+1;
    const button=add($("review-list"),"button","review-item"+(cursor===r.key?" active":""));button.type="button";
    button.setAttribute("aria-current",cursor===r.key?"true":"false");
    add(button,"strong",null,index+". "+r.cafe_name);
    add(button,"span",null,"확정 "+stats.labeled+" / 8 · 보류 "+stats.deferred+" · ID "+r.review_id);
    button.addEventListener("click",()=>{cursor=r.key;selectedQuote="";save();renderAll();});
  }
  if(!list.length)add($("review-list"),"p","empty","선택한 조건의 리뷰가 없습니다.");
  const index=list.findIndex(r=>r.key===cursor);
  $("previous").disabled=!list.length || index<=0;
  $("next").disabled=!list.length || index===list.length-1;
}
function renderReview(){
  const review=DATA.reviews.find(r=>r.key===cursor);$("aspect-list").replaceChildren();
  if(!review){$("review-title").textContent="선택한 조건의 리뷰가 없습니다";$("review-text").textContent="";$("review-source").textContent="";$("review-position").textContent="";return;}
  $("review-position").textContent=(DATA.reviews.indexOf(review)+1)+" / "+DATA.reviews.length+" 리뷰";
  $("review-title").textContent=review.cafe_name;$("review-source").textContent=review.source+" · 리뷰 "+review.review_id;
  $("review-text").textContent=review.text;
  for(const category of review.categories){
    const key=C.key(review,category),decision=decisions[key] || {label:"",evidence:"",notes:""};
    const row=add($("aspect-list"),"fieldset","aspect");row.disabled=!reviewer;
    const top=add(row,"div","aspect-top");add(top,"h3",null,DATA.categories[category]);
    const select=add(top,"select");select.setAttribute("aria-label",DATA.categories[category]+" 감성");
    let option=add(select,"option",null,"선택해주세요 · 미검토");option.value="";
    for(const [value,label] of Object.entries(C.LABELS)){option=add(select,"option",null,label);option.value=value;}
    select.value=decision.label;
    const badge=add(top,"span","aspect-status");
    const fields=add(row,"div","aspect-fields"),evidenceBox=add(fields,"div"),notesBox=add(fields,"div");
    const heading=add(evidenceBox,"div","evidence-header");const label=add(heading,"label",null,"원문 근거");label.htmlFor="evidence-"+category;
    const quote=add(heading,"button","quote-button","선택 구절 넣기");quote.type="button";
    const evidence=add(evidenceBox,"textarea");evidence.id="evidence-"+category;evidence.rows=2;evidence.maxLength=8000;evidence.value=decision.evidence;evidence.placeholder="원문 구절을 그대로 입력하세요";
    const noteLabel=add(notesBox,"label",null,"판단 보류 이유 / 메모");noteLabel.htmlFor="notes-"+category;
    const notes=add(notesBox,"textarea");notes.id="notes-"+category;notes.rows=2;notes.maxLength=8000;notes.value=decision.notes;notes.placeholder="모호한 대상·표현 또는 검토 메모";
    const validation=add(row,"p","validation");
    const status=()=>{
      const check=C.validate(review,{label:select.value,evidence:evidence.value,notes:notes.value});
      badge.textContent={pending:"미검토",invalid:"입력 미완료",labeled:"정답 확정",deferred:"판단 보류"}[check.status];
      validation.textContent=check.message;
    };
    const update=()=>{decisions[key]={label:select.value,evidence:evidence.value,notes:notes.value};status();save();renderProgress();renderList();};
    select.addEventListener("change",update);evidence.addEventListener("input",update);notes.addEventListener("input",update);
    quote.addEventListener("click",()=>{
      if(!selectedQuote || !review.text.includes(selectedQuote)){notice("먼저 위 원문에서 근거 구절을 선택해주세요.");return;}
      evidence.value=evidence.value.trim()?evidence.value+"\n"+selectedQuote:selectedQuote;update();notice("");
    });status();
  }
}
function renderAll(){renderProgress();renderList();renderReview();}
document.addEventListener("selectionchange",()=>{
  const selection=document.getSelection(),text=$("review-text");
  if(selection && !selection.isCollapsed && text.contains(selection.anchorNode) && text.contains(selection.focusNode))selectedQuote=selection.toString();
});
for(const id of ["cafe-filter","status-filter"])$(id).addEventListener("change",()=>{
  const list=filtered();if(!list.some(r=>r.key===cursor))cursor=list[0]?.key || "";selectedQuote="";save();renderAll();
});
function move(offset){const list=filtered(),index=list.findIndex(r=>r.key===cursor),target=list[index+offset];if(target){cursor=target.key;selectedQuote="";save();renderAll();}}
$("previous").addEventListener("click",()=>move(-1));$("next").addEventListener("click",()=>move(1));
$("next-pending").addEventListener("click",()=>{
  const start=DATA.reviews.findIndex(r=>r.key===cursor);
  const order=[...DATA.reviews.slice(start+1),...DATA.reviews.slice(0,start+1)];
  const next=order.find(r=>($("cafe-filter").value==="all" || r.cafe_id===$("cafe-filter").value) && !reviewCounts(r).finished_reviews);
  if(!next){notice("선택한 카페의 모든 리뷰를 검토했습니다.");return;}
  $("status-filter").value="remaining";cursor=next.key;selectedQuote="";save();renderAll();notice("");
});
function showFile(title,description,content,extension,mime){
  if(objectUrl)URL.revokeObjectURL(objectUrl);
  objectUrl=URL.createObjectURL(new Blob([content],{type:mime}));
  $("export-title").textContent=title;$("export-description").textContent=description;$("export-preview").value=content;
  $("save-file").href=objectUrl;$("save-file").download=("review_annotations_"+reviewer+"_"+DATA.dataset_sha256.slice(0,10)).replace(/[\\/:*?"<>|\u0000-\u001f]/g,"_")+"."+extension;
  $("export-dialog").showModal();
}
$("backup").addEventListener("click",()=>{save();showFile("진행 상황 JSON 저장","현재 입력과 검토 위치를 보관합니다. 이 저장본은 같은 리뷰 세트에서 다시 불러올 수 있습니다.",JSON.stringify(C.snapshot(DATA,reviewer,decisions,cursor),null,2),"json","application/json;charset=utf-8");});
$("export").addEventListener("click",()=>{
  try{const content=C.csv(DATA,reviewer,decisions),stats=C.counts(DATA.reviews,decisions);showFile("정답 CSV 내보내기","확정 "+stats.labeled+"항목 · 판단 보류 "+stats.deferred+"항목 · 미완료 "+(stats.pending+stats.invalid)+"항목. 판단 보류·미검토는 빈 라벨로 내보냅니다. 파일 저장이 어려우면 아래 내용을 복사할 수 있습니다.",content,"csv","text/csv;charset=utf-8");notice("");}
  catch(error){const first=DATA.reviews.find(r=>r.categories.some(category=>C.validate(r,decisions[C.key(r,category)]).status==="invalid"));if(first){$("cafe-filter").value=$("status-filter").value="all";cursor=first.key;renderAll();}notice(error.message);}
});
$("restore").addEventListener("change",async event=>{
  const file=event.target.files?.[0];if(!file)return;
  try{
    if(file.size>16*1024*1024)throw new Error("JSON 저장본은 16MB 이하로 선택해주세요.");
    const incoming=C.parseSnapshot(DATA,await file.text());
    const stored=readStorage(profileKey(incoming.reviewer));
    const before=stored?C.parseSnapshot(DATA,stored):{decisions:Object.create(null),cursor:DATA.reviews[0].key};
    const undo=JSON.stringify(C.snapshot(DATA,incoming.reviewer,before.decisions,before.cursor));
    try{localStorage.setItem(namespace+":before-import",undo);$("undo-import").hidden=false;}catch{throw new Error("변경 전 입력을 저장할 수 없어 불러오기를 중단했습니다. 진행 상황 JSON을 먼저 보관해주세요.");}
    activate(incoming.reviewer,incoming);notice("JSON 저장본을 불러왔습니다. ‘불러오기 전 입력 복구’로 변경 전 입력을 복구할 수 있습니다.");
  }catch(error){notice(error.message);}finally{event.target.value="";}
});
$("undo-import").hidden=!readStorage(namespace+":before-import");
$("undo-import").addEventListener("click",()=>{
  try{const saved=C.parseSnapshot(DATA,readStorage(namespace+":before-import"));activate(saved.reviewer,saved);notice("불러오기 전 입력을 복구했습니다.");}catch(error){notice(error.message);}
});
$("storage-status").textContent="검토자별로 별도 저장합니다. 정답은 자동으로 채우지 않습니다.";
renderAll();
