const FIRST_TIER_RESEARCH=new Set(['MSFT','AMZN','META','GOOGL','ORCL','SPACEX','NVDA','AVGO','AMD','MU','INTC','SKHX','SMSN']);
const legacyQuarterPanel=renderPanel;
function safeMarkdown(markdown){
  const safe=s=>esc(s).replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g,(_,label,url)=>`<a href="${url}" target="_blank" rel="noopener">${label}</a>`);
  return markdown.split(/\r?\n/).map(line=>{
    if(/^###? /.test(line))return `<h3>${safe(line.replace(/^#+ /,''))}</h3>`;
    if(/^# /.test(line))return `<h2>${safe(line.slice(2))}</h2>`;
    if(/^- /.test(line))return `<div class="md-item">• ${safe(line.slice(2))}</div>`;
    if(!line.trim())return '';
    return `<p>${safe(line).replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}</p>`;
  }).join('');
}
renderPanel=function(){
  for(const id of ['summary','pointsTitle','points','risks','source'])$(id)?.classList.remove('hidden');
  legacyQuarterPanel();
  if(!selected||!FIRST_TIER_RESEARCH.has(selected.ticker)||mode!=='formal'){
    $('quarterMarkdown')?.remove();return;
  }
  const record=QUARTER_RESEARCH[selected.id],stage=kind==='aftercheck'?'analysis':'preview';
  const item=record?.stages?.[stage],url=item?.path?'./'+item.path:null;
  const statusText={manual:'人工样稿',baseline_source_limited:'自动资料索引 · 等待完整研究',generated_review_pending:'自动草稿 · 待核',awaiting_official_source_packet:'等待官方资料',awaiting_model_credentials:'资料已备 · 等待模型配置',queued_call_limit:'资料已备 · 排队生成',source_review_pending:'来源逐值复核或官方正文待补',unavailable:'该阶段无同期稿',generation_failed:'生成失败 · 已保留旧稿',cutoff_after_event_date:'资料时间晚于财报日'}[item?.status]||item?.status||'待生成';
  for(const id of ['summary','metricWrap','pointsTitle','points','risks','sourceList','source','summaryBullets','toneLegend','metricTitleRow','marketFocusWrap','guidanceWrap','reactionWrap','sourceHeading'])$(id)?.classList.add('hidden');
  $('verdict').textContent=url?(item?.status==='baseline_source_limited'?'Markdown 资料索引':'Markdown 研究稿'):'尚无可阅读的 Markdown 研究稿';
  $('researchMeta').classList.remove('hidden');
  $('researchMeta').textContent=`${record?.quarter||'季度待核'} · ${stage==='preview'?(selected.status==='reported'?(item?.historical_reconstruction?'历史资料重建前瞻':'历史前瞻资料索引'):'财报前瞻'):'财报后分析'} · ${statusText}${item?.cutoff?' · 资料截止 '+item.cutoff:''}`;
  let box=$('quarterMarkdown');if(!box){box=document.createElement('div');box.id='quarterMarkdown';$('verdict').insertAdjacentElement('afterend',box)}
  const packetLink=item?.source_packet?` <a class="source" href="./${item.source_packet}" target="_blank">查看资料包 ↗</a>`:'';
  if(!url){box.innerHTML=`<p>本季度尚无合格的${stage==='preview'?(item?.historical_reconstruction?'历史资料重建':'同期财报前'):'财报后'}研究稿。历史结构化摘要不作为新稿展示。</p>${packetLink}`;return}
  box.innerHTML=`<a class="source" href="${url}" download>下载原始 Markdown ↓</a>${packetLink}<div class="md-body">正在读取文章…</div>`;
  box.dataset.path=url;
  fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.text()}).then(md=>{if(box.dataset.path===url)box.querySelector('.md-body').innerHTML=safeMarkdown(md)}).catch(e=>{if(box.dataset.path===url)box.querySelector('.md-body').textContent='文章读取失败：'+e.message});
};
