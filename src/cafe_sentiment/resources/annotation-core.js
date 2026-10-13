"use strict";
const AnnotationCore = (() => {
  const LABELS={positive:"긍정",negative:"부정",neutral:"명시적 중립",mixed:"긍부정 혼합",unscored:"평가 없음",deferred:"판단 보류"};
  const key=(review,category)=>JSON.stringify([review.source,review.cafe_id,review.review_id,category]);
  function validate(review, decision) {
    if (!decision || !decision.label) return {status:"pending",message:""};
    if (!Object.hasOwn(LABELS,decision.label)) return {status:"invalid",message:"감성 선택값을 확인해주세요."};
    if (decision.label==="deferred") return decision.notes?.trim() ? {status:"deferred",message:""} : {status:"invalid",message:"판단 보류 이유를 입력해주세요."};
    if (decision.label==="unscored") return {status:"labeled",message:""};
    const evidence=decision.evidence?.trim();
    if (!evidence) return {status:"invalid",message:"평가를 판단한 원문 구절을 입력해주세요."};
    if (!review.text.includes(evidence) && !evidence.split(/\r?\n/).filter(s=>s.trim()).every(s=>review.text.includes(s)))
      return {status:"invalid",message:"근거는 원문에서 그대로 가져와주세요. 여러 구절은 줄바꿈으로 구분합니다."};
    return {status:"labeled",message:""};
  }
  function counts(reviews, decisions) {
    const result={labeled:0,deferred:0,pending:0,invalid:0,finished_reviews:0,total:0};
    for (const review of reviews) {
      let finished=true;
      for (const category of review.categories) {
        const state=validate(review,decisions[key(review,category)]).status;
        result[state]++; result.total++;
        if (!["labeled","deferred"].includes(state)) finished=false;
      }
      if (finished) result.finished_reviews++;
    }
    return result;
  }
  function snapshot(data, reviewer, decisions, cursor) {
    return {schema_version:1,dataset_sha256:data.dataset_sha256,reviewer,saved_at:new Date().toISOString(),cursor,
      decisions:data.reviews.flatMap(review=>review.categories.map(category=>({source:review.source,cafe_id:review.cafe_id,
        review_id:review.review_id,category,...decisions[key(review,category)]}))).filter(row=>row.label || row.evidence || row.notes)};
  }
  function parseSnapshot(data, content) {
    const saved=typeof content==="string"?JSON.parse(content):content;
    if (saved.schema_version!==1 || saved.dataset_sha256!==data.dataset_sha256 || typeof saved.reviewer!=="string" || !saved.reviewer.trim() || saved.reviewer.length>80 || !Array.isArray(saved.decisions))
      throw new Error("현재 리뷰 세트의 올바른 JSON 저장본이 아닙니다.");
    const known=new Set(data.reviews.flatMap(review=>review.categories.map(category=>key(review,category)))), decisions=Object.create(null);
    for (const row of saved.decisions) {
      const identity=key(row,row.category);
      if (!known.has(identity) || Object.hasOwn(decisions,identity) || !["","positive","negative","neutral","mixed","unscored","deferred"].includes(row.label || ""))
        throw new Error("알 수 없거나 중복된 리뷰·항목이 있습니다.");
      for (const field of ["label","evidence","notes"]) if (row[field]!=null && (typeof row[field]!=="string" || row[field].length>20000)) throw new Error("저장된 입력값을 확인해주세요.");
      decisions[identity]={label:row.label || "",evidence:row.evidence || "",notes:row.notes || ""};
    }
    return {reviewer:saved.reviewer.trim(),decisions,cursor:data.reviews.some(r=>r.key===saved.cursor)?saved.cursor:data.reviews[0].key};
  }
  function csv(data, reviewer, decisions) {
    if (!reviewer.trim()) throw new Error("검토자 이름을 입력하고 검토를 시작해주세요.");
    const fields=["source","review_id","cafe_id","split","text","category","gold_label","evidence_text","reviewer","notes","input_text_sha256"];
    // Original text is represented by its hash and identity to avoid duplicating
    // raw reviews in a spreadsheet. The evaluator verifies this hash.
    const escape=value=>'"'+String(value??"").replace(/"/g,'""')+'"';
    const spreadsheetText=value=>/^[\s]*[=+\-@]/.test(value)?"'"+value:value;
    const rows=[];
    for (const review of data.reviews) for (const category of review.categories) {
      const decision=decisions[key(review,category)] || {}, check=validate(review,decision);
      if (check.status==="invalid") throw new Error("입력 미완료: "+review.review_id+" / "+data.categories[category]+" · "+check.message);
      const row={source:review.source,review_id:review.review_id,cafe_id:review.cafe_id,split:review.split,text:"",category,
        gold_label:check.status==="labeled"?decision.label:"",evidence_text:check.status==="labeled" && decision.label!=="unscored"?spreadsheetText(decision.evidence || ""):"",
        reviewer:["labeled","deferred"].includes(check.status)?spreadsheetText(reviewer):"",
        notes:spreadsheetText(check.status==="deferred"?"[판단 보류] "+decision.notes:decision.notes || ""),input_text_sha256:review.text_sha256};
      rows.push(fields.map(field=>escape(row[field])).join(","));
    }
    return "\uFEFF"+[fields.map(escape).join(","),...rows].join("\r\n");
  }
  return {LABELS,key,validate,counts,snapshot,parseSnapshot,csv};
})();
