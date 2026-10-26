"use strict";
const token=location.hash.slice(1)||sessionStorage.getItem('guaguaSetupToken')||'';
if(token)sessionStorage.setItem('guaguaSetupToken',token);
history.replaceState(null,"",location.pathname);
let current=0, state={}, loaded=false;
const $=id=>document.getElementById(id);
const steps=[
 ["環境準備","01 / FOUNDATION","從這裡，開始養一隻呱呱。","先安裝獨立執行環境。你的既有 Python、Conda 和機器人設定會保留。"],
 ["Discord 帳號","02 / CONNECT","給呱呱一個 Discord 身分。","在 Discord 官方開發者平台建立 Bot，再把它加入自己的伺服器。"],
 ["對話模型","03 / INTELLIGENCE","選擇適合你的大腦。","沒有顯示卡也能用 Gemini；希望在本機運算，可以選擇 LM Studio。"],
 ["搜尋服務","04 / DISCOVERY","讓回答，連上真實世界。","可選 Google 搜尋結果，也可以直接使用不需金鑰的 DuckDuckGo。"],
 ["音樂服務","05 / SOUND","讓伺服器，多一點旋律。","準備本機音樂執行環境，第一次需要下載 Java、Lavalink 與音源工具。"],
 ["檢查與啟動","06 / LAUNCH","準備好了，讓呱呱上線。","先確認帳號與模型連線，再啟動。帳號驗證成功不代表所有模型或音源都能使用。"]
];
const link=(url,text)=>`<a href="${url}" target="_blank" rel="noreferrer">${text} ↗</a>`;
function field(key,label,description="",secret=false){return `<label class="field">${label}<input data-key="${key}" ${secret?'type="password" autocomplete="new-password"':'type="text"'}><small>${description}</small></label>`;}
function render(){
 $("steps").innerHTML=steps.map((s,i)=>`<button data-step="${i}" class="${i===current?'active':''}" ${i===current?'aria-current="step"':''}><b>${i+1}</b>${s[0]}</button>`).join("");
 $("eyebrow").textContent=steps[current][1];$("title").textContent=steps[current][2];$("intro").textContent=steps[current][3];
 let html="";
 if(current===0) html=`<div class="cards"><div class="card"><span class="tag">ISOLATED RUNTIME</span><h3>Python 與執行套件</h3><p>建立專案專用 .bot-venv，再從 PyPI 安裝套件。首次可能需要數分鐘；不下載 PyTorch 等舊訓練套件。</p><button data-action="install">建立並安裝環境</button></div><div class="card"><span class="tag">BEFORE YOU START</span><h3>你需要準備</h3><p>Windows 10/11 x64、Python 3.11/3.12、網路，以及可管理的 Discord 伺服器。下載服務與模型需保留足夠磁碟空間。</p>${link('https://www.python.org/downloads/windows/','Python 官方下載')}</div></div><div class="note">下載後請先解壓縮完整專案，再執行 setup.bat。網頁只在 127.0.0.1 開啟；請保持精靈視窗執行。</div>`;
 if(current===1) html=`<div class="card"><h3>先在官方平台完成 3 件事</h3><ol><li>${link('https://discord.com/developers/applications','開啟 Discord Developer Portal')}，選 New Application，建立自己的應用。</li><li>到 Bot 頁面取得 Bot Token，啟用 <strong>Message Content Intent</strong> 與 <strong>Server Members Intent</strong>。</li><li>填入下方後，最後一步的連線檢查會產生邀請網址；邀請到你可管理的伺服器。</li></ol>${field('DISCORD_TOKEN','Discord Bot Token','使用 Bot Token，不是 Client Secret，也不是個人帳號 Token。留空會保留已存金鑰。',true)}</div>`;
 if(current===2) html=`<div class="card"><label class="field">模型運算方式<select data-key="DEFAULT_LLM_TYPE"><option value="gemini">Gemini · 雲端，無需本機 GPU</option><option value="local">LM Studio · 本機，需自行下載模型</option></select></label><div id="gemini-fields">${link('https://aistudio.google.com/apikey','建立 Gemini API Key')}${field('GEMINI_API_KEY','Gemini API Key','帳戶資格、地區與額度依 Google 當前規則。',true)}${field('GEMINI_MODEL','模型名稱','預設 gemini-2.5-flash；請確認帳戶可使用該模型。')}</div><div id="local-fields"><p>${link('https://lmstudio.ai/download','下載 LM Studio')}。安裝後先開啟一次，下載支援工具呼叫的聊天模型，以及 text-embedding-nomic-embed-text-v1.5。掃描文件辨識還需要視覺模型。</p>${field('LMSTUDIO_MODEL_KEY','已下載的模型 ID','依 LM Studio 顯示的實際模型 ID 填寫，不會自動下載大型模型。')}${field('LMSTUDIO_MODEL','提供給 Bot 的模型別名')}${field('LMSTUDIO_API_URL','本機 API 網址','只接受本機 HTTP；預設連接 1234 port。')}${field('LMSTUDIO_API_KEY','LM Studio API Token（選填）','有啟用 API 驗證時填入。',true)}${field('LMSTUDIO_CONTEXT_LENGTH','上下文長度','預設 32768，硬體記憶體不足時可調低；較小容量也會限制文件處理。')}<button data-action="model">儲存並啟動已下載的本機模型</button></div></div><div class="note">登入與同意條款均在官方網站／應用完成。精靈不會代辦付費方案，也不會保證每台電腦都能跑相同模型。</div>`;
 if(current===3) html=`<div class="cards"><div class="card"><span class="tag">OPTIONAL</span><h3>Google · 透過 SerpApi</h3><p>填入 Key 後優先使用 Google 結果。額度不足、連線錯誤或查無結果時，切換 DuckDuckGo。</p>${link('https://serpapi.com/users/sign_up','申請 SerpApi 帳號')}<br>${link('https://serpapi.com/manage-api-key','查看 API Key')}</div><div class="card"><span class="tag">READY WITHOUT A KEY</span><h3>DuckDuckGo 備援</h3><p>第一次使用可以跳過 SerpApi，直接保留空白即可搜尋。網站與搜尋服務仍可能限制流量或暫時不可用。</p>${link('https://serpapi.com/pricing','查看最新方案與額度')}</div></div>${field('SERPAPI_API_KEY','SerpApi API Key（選填）','留空保留已存金鑰。要停用已設定的服務，請手動清空 .env 對應欄位。',true)}`;
 if(current===4) html=`<div class="card"><h3>安裝音樂執行環境</h3><p>沿用專案現有安裝器，下載可攜式 Java 21、Lavalink、YouTube 插件與音源解析工具到專案資料夾。不改動系統 PATH；首次下載較久。</p><button data-action="music">準備音樂服務</button><p>目前 Windows x64 的自動化支援較完整。防火牆請保持本機服務僅供本機連線。</p></div><div class="note">YouTube 的登入／地區／音源限制無法由安裝器解決。可先用 SoundCloud 測試，使用音樂指令前請加入語音頻道。</div>`;
 if(current===5) html=`<div class="card"><h3>最後確認</h3><ol><li>儲存設定並執行檢查，邀請網址會顯示在下方紀錄。</li><li>將 Bot 加入伺服器，確認兩項 Intent 已啟用。</li><li>完成音樂環境安裝，確認沒有其他機器人程序正在執行，再按啟動。</li><li>在 Discord 輸入 <strong>@呱呱 你好</strong>；加入語音後試 <strong>/play</strong>。</li></ol><div class="inline-actions"><button data-action="check">儲存並檢查連線</button><button data-action="start">啟動機器人</button><button data-action="stop" class="secondary">停止本精靈啟動的程序</button></div></div><div class="note">程序啟動後，仍需在 Discord 確認上線。關閉網頁不會自動停止 Bot；不要和原有啟動腳本重複啟動。此精靈不會替你終止外部啟動的程序。</div>`;
 $("panel").innerHTML=html;
 for(const input of document.querySelectorAll('[data-key]')){
  const key=input.dataset.key;
  if(input.type==='password') input.placeholder=state.settings?.[key]?'已設定 · 留空保留':'尚未設定';
  else input.value=state.settings?.[key]??'';
 }
 toggleModel();$("back").disabled=current===0;$("next").textContent=current===5?'儲存設定 ✓':'儲存並繼續 →';
 updateBusy();
}
function toggleModel(){if($('local-fields')){const local=document.querySelector('[data-key="DEFAULT_LLM_TYPE"]').value==='local';$('local-fields').hidden=!local;$('gemini-fields').hidden=local;}}
async function api(path,data){const response=await fetch('/api/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Setup-Token':token},body:data?JSON.stringify(data):undefined});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
async function save(){const values={};document.querySelectorAll('[data-key]').forEach(input=>{values[input.dataset.key]=input.value;});if(Object.keys(values).length)await api('settings',values);}
function updateBusy(){document.querySelectorAll('[data-action]').forEach(button=>button.disabled=!!state.busy);$('next').disabled=!!state.busy;}
async function poll(){try{state=await api('state');if(!loaded){render();loaded=true;}updateBusy();$('job-status').textContent=state.status;$('running').textContent=state.running?'BOT PROCESS RUNNING':'LOCAL SESSION';$('logs').textContent=state.logs.length?state.logs.join('\n'):'等待操作。金鑰不會顯示在執行紀錄。';$('logs').scrollTop=$('logs').scrollHeight;}catch(error){$('notice').textContent=error.message+'；若精靈已關閉，請重新執行 setup.bat。';}finally{setTimeout(poll,1800);}}
document.addEventListener('change',event=>{if(event.target.dataset.key==='DEFAULT_LLM_TYPE')toggleModel();});
document.addEventListener('click',async event=>{const button=event.target.closest('button');if(!button)return;try{$('notice').textContent='';if(button.dataset.step!==undefined){await save();state=await api('state');current=Number(button.dataset.step);render();}if(button.dataset.action){await save();await api('action',{action:button.dataset.action});state.busy=true;updateBusy();}}catch(error){$('notice').textContent=error.message;}});
$('back').onclick=async()=>{try{await save();state=await api('state');current=Math.max(0,current-1);render();}catch(error){$('notice').textContent=error.message;}};
$('next').onclick=async()=>{try{await save();state=await api('state');if(current<5){current++;render();}else $('notice').textContent='設定已儲存。';}catch(error){$('notice').textContent=error.message;}};
if(!token){$('notice').textContent='缺少本機工作階段，請透過 setup.bat 重新開啟。';render();}else poll();
