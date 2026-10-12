"use strict";
const DATA = JSON.parse(document.getElementById("report-data").textContent);
const $ = id => document.getElementById(id);
const LABELS = DATA.category_labels;
const MIN = DATA.min_samples;
const nfmt = n => Number(n || 0).toLocaleString("ko-KR");
const sfmt = n => n == null ? "—" : Number(n).toFixed(1);
const add = (parent, tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  parent.append(node);
  return node;
};
let currentCafe, currentRows, currentPeriods;
const stateLabels = {positive:"긍정",negative:"부정",neutral:"중립",mixed:"혼합",unscored:"미판정"};

function option(select, value, label) {
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  select.append(node);
}
for (const cafe of DATA.cafes) option($("cafe-select"), cafe.id, cafe.name);
for (const [key,label] of Object.entries(LABELS)) {
  option($("trend-category"),key,label);
  option($("evidence-category"),key,label);
}
const requestedCafe = new URLSearchParams(location.hash.replace(/^#/, "")).get("cafe");
if (DATA.cafes.some(cafe => cafe.id === requestedCafe)) $("cafe-select").value = requestedCafe;
else if (DATA.cafes.length) $("cafe-select").value = [...DATA.cafes].sort((a,b) => (b.periods.all?.stats.total || 0) - (a.periods.all?.stats.total || 0))[0].id;

function merge(category, periods) {
  const rows = periods.map(key => currentCafe.periods[key]?.categories[category]).filter(Boolean);
  const base = {category,category_label:LABELS[category],cafe_id:currentCafe.id,cafe_name:currentCafe.name,
    total_reviews:0,mentioned_reviews:0,scored_reviews:0,polarity_sum:0,positive_reviews:0,negative_reviews:0,neutral_reviews:0,mixed_reviews:0,
    themes:{positive:[],negative:[]},examples:{positive:[],negative:[]}};
  for (const row of rows) for (const key of ["total_reviews","mentioned_reviews","scored_reviews","polarity_sum","positive_reviews","negative_reviews","neutral_reviews","mixed_reviews"]) base[key] += row[key] || 0;
  base.score = base.scored_reviews ? 50 + 25 * base.polarity_sum / base.scored_reviews : null;
  base.sample_status = !base.scored_reviews ? "평가 근거 없음" : base.scored_reviews < MIN ? "표본 부족" : "집계 가능";
  for (const direction of ["positive","negative"]) {
    const themes = new Map(), samples = new Map();
    for (const row of rows) {
      for (const item of row.themes[direction]) themes.set(item.name,(themes.get(item.name) || 0) + item.reviews);
      for (const item of row.examples[direction]) samples.set(item.source + ":" + item.review_id,item);
    }
    base.themes[direction] = [...themes].map(([name,reviews]) => ({name,reviews})).sort((a,b) => b.reviews-a.reviews || a.name.localeCompare(b.name,"ko")).slice(0,8);
    base.examples[direction] = [...samples.values()].sort((a,b) => (b.date || "").localeCompare(a.date || "") || b.review_id.localeCompare(a.review_id)).slice(0,DATA.example_limit);
  }
  return base;
}
function selectCafe() {
  currentCafe = DATA.cafes.find(cafe => cafe.id === $("cafe-select").value);
  for (const id of ["start-select","end-select"]) $(id).replaceChildren();
  if (!currentCafe) {render(); return;}
  const months = Object.keys(currentCafe.periods).filter(key => /^\d{4}-\d{2}$/.test(key)).sort();
  for (const month of months) for (const id of ["start-select","end-select"]) option($(id),month,month);
  if (months.length) $("end-select").value = months.at(-1);
  $("scope-select").options[1].disabled = !months.length;
  if (!months.length) $("scope-select").value = "all";
  render();
}
function render() {
  if (!currentCafe) {
    $("cafe-title").textContent = "분석 가능한 리뷰가 없습니다";
    $("scope-note").textContent = "입력 오류 기록과 필수값을 확인해주세요.";
    return;
  }
  const all = $("scope-select").value === "all";
  const months = Object.keys(currentCafe.periods).filter(key => /^\d{4}-\d{2}$/.test(key)).sort();
  $("start-select").disabled = $("end-select").disabled = all;
  const invalid = !all && $("start-select").value > $("end-select").value;
  $("filter-error").hidden = !invalid;
  document.querySelector("main").classList.toggle("invalid-filter", invalid);
  $("print-report").disabled = invalid;
  if (invalid) {
    $("filter-error").textContent = "시작 월을 종료 월보다 앞서거나 같은 월로 선택해주세요.";
    $("download-csv").disabled = true;
    $("period-caption").textContent = "월 범위 선택을 확인해주세요.";
    $("scope-note").textContent = "유효한 범위를 선택하면 결과를 다시 표시합니다.";
    return;
  }
  $("download-csv").disabled = false;
  currentPeriods = all ? ["all"] : months.filter(key => key >= $("start-select").value && key <= $("end-select").value);
  currentRows = Object.keys(LABELS).map(category => merge(category,currentPeriods));
  $("cafe-title").textContent = currentCafe.name;
  $("data-badge").textContent = DATA.is_synthetic ? "자체 작성 생성 예제" : "입력 리뷰 기반 참고 분석";
  const selection = all ? "전체 기간" : $("start-select").value + " ~ " + $("end-select").value;
  $("period-caption").textContent = selection + "  ·  " + (currentCafe.date_start ? "작성일 관측 " + currentCafe.date_start + " ~ " + currentCafe.date_end : "확인된 작성일 없음");
  const stats = {total:0,dated:0,scored:0,needs_review:0}, sources = new Map();
  for (const key of currentPeriods) {
    const bucket = currentCafe.periods[key];
    if (!bucket) continue;
    for (const field of Object.keys(stats)) stats[field] += bucket.stats[field] || 0;
    for (const [source,n] of Object.entries(bucket.sources)) sources.set(source,(sources.get(source) || 0)+n);
  }
  const dateNote = DATA.start || DATA.end ? "실행 시 날짜 필터가 있어 날짜 미상 리뷰는 전체 기간에서도 제외했습니다." :
    all ? "날짜 미상 리뷰도 전체 기간에 포함합니다." : "월 범위에서는 날짜 미상 리뷰를 제외합니다.";
  $("scope-note").textContent = dateNote + " 해당 카페 날짜 미상 " + nfmt(currentCafe.missing_dates) + "건 · 출처 " + ([...sources].map(([name,n]) => name + " " + nfmt(n) + "건").join(", ") || "선택 범위 자료 없음");
  $("kpis").replaceChildren();
  for (const [number,label] of [[stats.total,"선택 범위 리뷰"],[stats.dated,"작성일이 확인된 리뷰"],[stats.scored,"감성 근거가 있는 리뷰"],[stats.needs_review,"일부 근거 확인 필요"]]) {
    const box = add($("kpis"),"div","kpi");
    add(box,"strong",null,nfmt(number) + "건");
    add(box,"span","label",label);
  }
  renderCards(); renderActions(); renderTrend(); renderEvidence();
  $("quality-note").textContent = "현재 사전은 사람 검증 전 후보입니다. 날짜·대상·인용·반어를 놓칠 수 있습니다. 항목별 " + MIN + "건 미만은 임시 기준으로 표본 부족을 표시하며, 그 이상도 정확도를 보장하지 않습니다.";
  $("provenance").textContent = "분석기 " + DATA.version + " · 생성 " + DATA.generated_at.slice(0,10) + " · 사전 " + DATA.lexicon_sha256.slice(0,12) + " · 입력 " + DATA.input_sha256.slice(0,12) + (DATA.example_limit ? " · 일부 리뷰 발췌 포함" : " · 리뷰 발췌 제외");
  document.title = currentCafe.name + " · 카페 리뷰 진단";
}
function renderCards() {
  $("category-cards").replaceChildren();
  for (const row of currentRows) {
    const card = add($("category-cards"),"button","category-card");
    card.type="button";
    card.setAttribute("aria-label",row.category_label + " 점수 " + sfmt(row.score) + ", " + row.sample_status + ", 근거 보기");
    add(card,"h3",null,row.category_label);
    const line = add(card,"div","score-line");
    add(line,"strong",null,sfmt(row.score));
    add(line,"span",null,row.score == null ? "점수 없음" : "/ 100");
    add(card,"p","sample" + (row.scored_reviews && row.scored_reviews < MIN ? " low" : ""),row.sample_status + " · 판정 " + nfmt(row.scored_reviews) + "건 / 언급 " + nfmt(row.mentioned_reviews) + "건");
    const bar = add(card,"div","sentiment-bar");
    bar.setAttribute("aria-hidden","true");
    for (const kind of ["positive","negative","neutral","mixed"]) {
      const segment = add(bar,"span","segment-" + kind);
      segment.style.width = (row.scored_reviews ? row[kind+"_reviews"] / row.scored_reviews * 100 : 0) + "%";
    }
    add(card,"p","legend","긍정 " + row.positive_reviews + " · 부정 " + row.negative_reviews + " · 중립 " + row.neutral_reviews + " · 혼합 " + row.mixed_reviews);
    card.addEventListener("click",() => {
      $("trend-category").value = $("evidence-category").value = row.category;
      renderTrend(); renderEvidence();
      $("evidence-category").scrollIntoView({behavior:"smooth",block:"center"});
    });
  }
}
const ADVICE = {menu:"취향 차이인지 제공 상태 문제인지 해당 메뉴의 원문과 현장 상태를 함께 확인해보세요.",service:"응대·설명·요청 처리 중 어떤 상황이 반복되는지 확인해보세요.",space:"좌석·소음·작업 편의 중 반복되는 표현을 실제 이용 상황과 대조해보세요.",location:"주차·찾아오는 길 안내가 실제 방문 상황과 맞는지 확인해보세요.",value:"가격·양·구성에 대한 기대와 실제 제공 내용을 원문에서 확인해보세요.",hygiene:"관련 식기·청소·화장실 상태를 확인해보세요. 감성 표현만으로 상태를 확정하지 않습니다.",operation:"주문·대기·픽업 과정에서 해당 표현이 반복되는 구간을 현장에서 확인해보세요.",overall:"다른 항목의 근거를 함께 읽어 재방문 의사와 전체 경험의 이유를 확인해보세요."};
function renderActions() {
  for (const direction of ["negative","positive"]) {
    const container = direction === "negative" ? $("actions") : $("strengths");
    container.replaceChildren();
    const candidates = currentRows.filter(row => row.scored_reviews >= MIN && row[direction+"_reviews"]+row.mixed_reviews >= 3)
      .sort((a,b) => (b[direction+"_reviews"]+b.mixed_reviews)-(a[direction+"_reviews"]+a.mixed_reviews)).slice(0,3);
    if (!candidates.length) {
      add(container,"p","empty",direction === "negative" ? "표본과 반복 근거가 부족해 개선 우선순위를 정하지 않았습니다. 아래 개별 근거부터 확인해주세요." : "표본과 반복 근거가 부족해 공통 강점을 확정하지 않았습니다.");
      continue;
    }
    for (const row of candidates) {
      const box = add(container,"div","action");
      const count = row[direction+"_reviews"] + row.mixed_reviews;
      add(box,"h3",direction,row.category_label + " · " + stateLabels[direction] + " 포함 " + nfmt(count) + "건");
      add(box,"p",null,"해당 항목 판정 " + nfmt(row.scored_reviews) + "건 중 " + Math.round(count/row.scored_reviews*100) + "% · " + (row.themes[direction].slice(0,2).map(item => item.name + " " + item.reviews + "건").join(" / ") || "관련 근거를 확인해주세요."));
      if (direction === "negative") add(box,"p",null,ADVICE[row.category]);
    }
  }
}
function svgNode(parent,name,attributes,text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg",name);
  for (const [key,value] of Object.entries(attributes || {})) node.setAttribute(key,String(value));
  if (text != null) node.textContent=text;
  parent.append(node); return node;
}
function renderTrend() {
  if (!currentCafe) return;
  const category = $("trend-category").value;
  const months = Object.keys(currentCafe.periods).filter(key => /^\d{4}-\d{2}$/.test(key)).sort().filter(key => $("scope-select").value === "all" || (key >= $("start-select").value && key <= $("end-select").value));
  const rows = months.map(key => currentCafe.periods[key].categories[category]);
  $("trend-table").replaceChildren(); $("trend-chart").replaceChildren();
  for (const row of rows) {
    const tr = add($("trend-table"),"tr");
    for (const value of [row.period,sfmt(row.score),nfmt(row.scored_reviews),nfmt(row.total_reviews),row.sample_status]) add(tr,"td",null,value);
  }
  const pairs = rows.slice(1).map((row,i) => [rows[i],row]).filter(pair => pair.every(row => row.scored_reviews >= MIN));
  if (!pairs.length) {
    $("trend-note").textContent = "추세 판단 보류 · 연속된 두 월에 각각 " + MIN + "건 이상의 판정 근거가 필요합니다. 날짜 미상 리뷰는 월별에서 제외합니다.";
    add($("trend-chart"),"p","empty","현재 자료로 월별 변화를 확정하기 어렵습니다. 아래 월별 건수를 함께 확인해주세요.");
    return;
  }
  $("trend-note").textContent = "각 월에 판정 " + MIN + "건 이상인 구간만 연결합니다. 빈 달·작은 표본은 선으로 이어 추정하지 않습니다.";
  const svg = svgNode($("trend-chart"),"svg",{viewBox:"0 0 960 240",role:"img","aria-label":LABELS[category]+" 월별 점수. 근거가 충분한 월만 표시"});
  const left=44,right=940,top=20,bottom=190;
  const x=i => left+(right-left)*(rows.length===1 ? .5 : i/(rows.length-1));
  const y=score => bottom-(bottom-top)*score/100;
  for (const score of [0,25,50,75,100]) {
    svgNode(svg,"line",{x1:left,x2:right,y1:y(score),y2:y(score),class:"axis"});
    svgNode(svg,"text",{x:30,y:y(score)+4,"text-anchor":"end"},score);
  }
  let path="",previous=false;
  rows.forEach((row,i) => {
    const usable=row.scored_reviews>=MIN && row.score!=null;
    if (usable) {
      path += (previous ? " L" : " M")+x(i)+" "+y(row.score);
      const dot=svgNode(svg,"circle",{cx:x(i),cy:y(row.score),r:4,class:"point"});
      svgNode(dot,"title",{},row.period+" · "+sfmt(row.score)+"점 · 판정 "+row.scored_reviews+"건");
    }
    previous=usable;
    if (i===0 || i===rows.length-1 || i % Math.max(1,Math.ceil(rows.length/8))===0) svgNode(svg,"text",{x:x(i),y:218,"text-anchor":i===0?"start":i===rows.length-1?"end":"middle"},row.period);
  });
  svgNode(svg,"path",{d:path,class:"score-path"});
}
function renderEvidence() {
  const row = currentRows?.find(row => row.category === $("evidence-category").value);
  if (!row) return;
  for (const direction of ["positive","negative"]) {
    const tags=$(direction+"-themes"),container=$(direction+"-examples");
    tags.replaceChildren(); container.replaceChildren();
    for (const item of row.themes[direction]) add(tags,"span","theme-tag",item.name+" · "+item.reviews+"건");
    if (!row.examples[direction].length) add(container,"p","nosamples",DATA.example_limit ? "선택 범위에서 판정 가능한 "+stateLabels[direction]+" 근거가 없습니다." : "이 보고서는 리뷰 발췌를 제외하고 생성했습니다.");
    for (const item of row.examples[direction]) {
      const box=add(container,"article","example "+direction);
      add(box,"p","meta",(item.date || "작성 연도 미상")+" · "+item.source+" · "+stateLabels[item.label]+" 평가");
      const text=add(box,"p");
      if (item.leading_ellipsis) text.append(document.createTextNode("…"));
      let cursor=0;
      for (const mark of [...item.marks].sort((a,b) => a.start-b.start)) {
        if (mark.start<cursor || mark.start<0 || mark.end>item.snippet.length || mark.end<mark.start) continue;
        text.append(document.createTextNode(item.snippet.slice(cursor,mark.start)));
        const highlight=add(text,"mark",null,item.snippet.slice(mark.start,mark.end));
        highlight.title=mark.expression;
        cursor=mark.end;
      }
      text.append(document.createTextNode(item.snippet.slice(cursor)));
      if (item.trailing_ellipsis) text.append(document.createTextNode("…"));
    }
  }
}
function csvCell(value) {
  let text=value == null ? "" : String(value);
  if (typeof value === "string" && /^[=+\-@\t\r\n]/.test(text)) text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
}
let csvUrl;
function downloadCsv() {
  if (!currentRows) return;
  const fields=["cafe_id","cafe_name","period","category","category_label","score","total_reviews","mentioned_reviews","scored_reviews","positive_reviews","negative_reviews","neutral_reviews","mixed_reviews","sample_status"];
  const period=$("scope-select").value==="all"?"all":$("start-select").value+"~"+$("end-select").value;
  const rows=currentRows.map(row => ({...row,period,score:row.score==null?null:Number(row.score.toFixed(2))}));
  const content="\uFEFF"+[fields.map(csvCell).join(","),...rows.map(row => fields.map(key => csvCell(row[key])).join(","))].join("\r\n");
  if (csvUrl) URL.revokeObjectURL(csvUrl);
  csvUrl=URL.createObjectURL(new Blob([content],{type:"text/csv;charset=utf-8"}));
  $("csv-preview").value=content;
  $("csv-save").href=csvUrl;
  $("csv-save").download=(currentCafe.name+"_리뷰진단_"+period).replace(/[\\/:*?"<>|\u0000-\u001f]/g,"_")+".csv";
  $("csv-dialog").showModal();
}
$("cafe-select").addEventListener("change",selectCafe);
for (const id of ["scope-select","start-select","end-select"]) $(id).addEventListener("change",render);
$("trend-category").addEventListener("change",renderTrend);
$("evidence-category").addEventListener("change",renderEvidence);
$("download-csv").addEventListener("click",downloadCsv);
$("print-report").addEventListener("click",() => window.print());
selectCafe();
