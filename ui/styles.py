"""Shared dashboard stylesheet."""

from __future__ import annotations

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
:root{--ink:#141516;--muted:#92959a;--line:#ececef;--paper:#fff;--canvas:#fff;--outer:#fff;--blue:#4351c6;--primary-color:#4351c6;--card-edge:#e3efe4;--card-glow:rgba(105,166,116,.07)}
html,body,[class*="css"]{font-family:'Poppins',sans-serif;color:var(--ink)}
.stApp,.stAppViewContainer,.stMain{background:var(--outer)}
header[data-testid="stHeader"]{height:0;background:transparent;visibility:hidden}
div[data-testid="stToolbar"]{display:none}
.block-container{max-width:1560px!important;padding:0!important;margin:28px auto!important;background:transparent!important;min-height:0!important}
.st-key-dashboard-layout{background:#fff;border-radius:38px;box-shadow:none;height:auto!important;overflow:visible;min-height:calc(100vh - 56px)}
.st-key-dashboard-layout div[data-testid="stHorizontalBlock"]:has(>div[data-testid="stColumn"] .st-key-dashboard-sidebar){gap:0!important;align-items:stretch}
.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-sidebar){background:linear-gradient(180deg,#e9f5fc 0%,#f1f8fc 34%,#f8fbfd 68%,#fff 100%);border-right:1px solid #d9eaf3;border-radius:38px 0 0 38px;box-sizing:border-box;flex:0 0 24%!important;max-width:24%;padding:34px 28px 36px}
.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-main){background:var(--canvas);border-radius:0 38px 38px 0;box-sizing:border-box;flex:1 1 74%!important;max-width:74%;padding:32px 42px 48px}
.st-key-dashboard-sidebar,.st-key-dashboard-main{width:100%}
.stMarkdown p{margin-bottom:.45rem}
.location-label,.eyebrow{font-size:12px!important;color:var(--muted)!important;letter-spacing:.01em}
.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"]{max-width:100%}
.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"] button,.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"] [role="radio"]{padding:7px 12px!important;font-size:12px!important;border-color:#e8e8eb!important;color:#5d6065!important;box-shadow:none!important}
.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"] button[aria-pressed="true"],.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"] button[aria-checked="true"],.st-key-dashboard-sidebar div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"]{background:#efeff1!important;color:#17181a!important;box-shadow:none!important}
.st-key-mode-switch div[data-testid="stSegmentedControl"]{margin:0 0 18px}
.st-key-mode-switch div[data-testid="stSegmentedControl"] button,.st-key-mode-switch div[data-testid="stSegmentedControl"] [role="radio"]{border:0!important;border-radius:0!important;background:transparent!important;padding:8px 0 10px!important;margin:0 24px 0 0!important;color:#999ca1!important;font-size:17px!important;font-weight:600!important;box-shadow:none!important}
.st-key-mode-switch div[data-testid="stSegmentedControl"] button[aria-pressed="true"],.st-key-mode-switch div[data-testid="stSegmentedControl"] button[aria-checked="true"],.st-key-mode-switch div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"]{color:#111!important;border-bottom:1.5px solid #111!important;background:transparent!important}
.stSelectbox label{font-size:11px!important;color:#83868b!important}
.stSelectbox div[data-baseweb="select"]>div{min-height:34px;border:1px solid #e8e8eb!important;border-radius:8px!important;background:#fff!important}
.st-key-dashboard-layout div[data-baseweb="select"]>div,.st-key-today-planner-form div[data-baseweb="select"]>div,.st-key-dashboard-layout [data-testid="stTimeInput"] input,.st-key-today-planner-form [data-testid="stTimeInput"] input{background:#fff!important}
[data-baseweb="popover"] [role="listbox"],[data-baseweb="popover"] [role="option"],[data-baseweb="menu"]{background:#fff!important}
.weather-hero{padding-top:34px}
.weather-hero>.weather-icon{width:226px;height:205px;display:block;object-fit:contain;margin:0 auto}
.weather-hero .temperature{font-family:'Poppins',sans-serif;font-weight:300;font-size:88px;line-height:1;letter-spacing:-5px;margin:12px 0 26px;color:#111}
.weather-hero .date{font-size:18px;color:#222}
.weather-hero .date span{color:#999ca1}
.side-divider{height:1px;background:#ededee;margin:24px 0}
.side-line{display:flex;align-items:center;gap:12px;font-size:14px;margin:14px 0;color:#242528}
.side-line strong{font-weight:600;color:#242528}
.side-line .weather-icon{width:24px;height:24px;object-fit:contain;flex:0 0 24px}
.side-advice{align-items:flex-start;line-height:1.55;margin-top:22px!important}
.side-advice-icon{width:23px;height:23px;object-fit:contain;flex:0 0 23px;margin-top:1px}
.city-tile{position:relative;overflow:hidden;height:110px;border-radius:16px;background:#d9e3e3;margin-top:46px;padding:0}
.city-tile .caption{position:absolute;left:18px;bottom:13px;color:#fff;font-size:14px;font-weight:600;text-shadow:0 1px 7px #1f293780}
.city-tile svg{width:100%;height:100%;display:block}
.aqi-number{font-family:'Poppins',sans-serif;font-size:90px;line-height:1;font-weight:300;letter-spacing:-5px;margin:14px 0 4px}
.aqi-number-ring{width:144px;height:144px;margin:0 auto 10px;border:2px solid var(--aqi-color,#c77d3d);border-radius:50%;box-shadow:0 0 0 8px #f5f5f7,0 10px 28px #2021240c;display:grid;place-items:center;background:#fff;box-sizing:border-box}
.aqi-number-ring .aqi-number{font-size:52px;line-height:1;font-weight:500;letter-spacing:-2px;margin:0;color:#17181a;font-variant-numeric:tabular-nums}
.daily-average-card{align-items:stretch}
.daily-aqi-content{display:grid;place-items:center;flex:1}
.daily-aqi-ring{width:126px;height:126px;border:2px solid var(--aqi-color,#c77d3d);border-radius:50%;box-shadow:0 0 0 7px #f6f6f8;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff;box-sizing:border-box}
.daily-aqi-ring strong{font-family:'Poppins',sans-serif;font-size:38px;line-height:1.1;font-weight:500;letter-spacing:-1px;color:#17181a;font-variant-numeric:tabular-nums}
.daily-aqi-ring span{font-size:10px;color:#898c91;margin-top:4px}
.time-insight-card{align-items:center;text-align:center}
.time-insight-card .metric-label{justify-content:center;text-align:center;width:100%;min-height:42px}
.time-insight-main{display:flex;align-items:center;justify-content:center;gap:12px;min-height:72px;width:100%}
.time-insight-icon{width:42px;height:42px;object-fit:contain;display:block;flex:0 0 42px}
.time-insight-card .metric-value{font-size:36px!important;text-align:center}
.time-insight-card .metric-foot{text-align:center;max-width:260px;font-weight:600;color:#303237}
.st-key-aqi-insights-grid .metric-card.compact .metric-foot,.st-key-aqi-insights-grid .pm25-advice,.st-key-aqi-insights-grid .advice-copy{font-weight:600;color:#303237}
.st-key-aqi-insights-grid .metric-card.compact{align-items:center;text-align:center}
.st-key-aqi-insights-grid .metric-card.compact .metric-label{justify-content:center;text-align:center;width:100%}
.st-key-aqi-insights-grid .pm25-card .pm25-details{align-self:stretch;text-align:center}
.st-key-health-advisory{align-items:center;text-align:center}
.st-key-health-advisory>div[data-testid="stVerticalBlock"]{align-items:center;text-align:center}
.st-key-health-advisory .metric-label{justify-content:center;text-align:center;width:100%}
.st-key-health-advisory .stSelectbox{width:min(100%,280px);align-self:center;text-align:left}
.st-key-health-advisory .advice-copy{width:100%;text-align:center}
.air-info{position:relative;display:inline-flex;align-items:center;flex:0 0 auto;z-index:2}
.air-info[open]{z-index:30}
.air-info summary{list-style:none;width:19px;height:19px;border:1px solid #c9cdd3;border-radius:50%;display:grid;place-items:center;box-sizing:border-box;color:#747982;font-size:12px;font-weight:600;line-height:1;cursor:pointer;user-select:none}
.air-info summary::-webkit-details-marker{display:none}
.air-info summary:hover,.air-info[open] summary{border-color:#7f8791;color:#22262b;background:#f7f8f9}
.air-info-note{position:absolute;left:-8px;top:calc(100% + 8px);width:min(330px,calc(100vw - 48px));max-height:min(65vh,420px);overflow:auto;padding:16px 18px;background:#fff;border:1px solid #e7e9ed;border-radius:14px;box-shadow:0 12px 34px #1c25301f;color:#36393e;font-size:12px;font-weight:400;line-height:1.55;text-align:left;z-index:31}
.air-info-note strong{display:block;color:#202226;font-size:13px;margin:0 0 5px}
.air-info-note p{margin:0 0 9px!important}
.air-info-note ul{margin:6px 0 10px;padding-left:17px}
.air-info-note li{margin:0 0 5px}
.air-info-sources{font-size:10px;color:#878b92;border-top:1px solid #eff0f2;padding-top:8px;margin-top:10px}
.air-info-sources a{color:#686f7d;text-decoration:underline}
.aqi-unit-with-help{display:flex;align-items:center;justify-content:center;gap:6px}
.aqi-unit{color:#7c7f84;font-size:12px;letter-spacing:.02em}
.aqi-category{font-size:20px;font-weight:600;margin:8px 0 0}
.aqi-meta{font-size:12px;color:#85888d;line-height:1.55;margin-top:11px}
.air-illustration{height:205px;display:flex;align-items:center;justify-content:center;margin:20px 0 8px}
.section-title{font-size:18px;font-weight:600;letter-spacing:-.35px;margin:26px 0 14px}
.forecast-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.aqi-forecast-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.forecast-card{background:#fff;border:2px solid var(--card-edge);border-radius:15px;min-height:137px;text-align:center;padding:13px 5px 11px;box-shadow:0 2px 10px var(--card-glow);transition:border-color .22s ease,box-shadow .22s ease}
.forecast-day{font-size:12px;color:#27282a;font-weight:500}
.forecast-date{font-size:10px;color:#989ba0;margin-top:2px}
.forecast-icon{height:48px;display:flex;justify-content:center;align-items:center;margin:7px auto 5px}
.forecast-icon .weather-icon{width:46px;height:46px;object-fit:contain}
.forecast-icon .aqi-weather-icon{width:48px;height:48px;object-fit:contain}
.forecast-value{font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.forecast-sub{font-size:10px;color:#888b90;margin-top:4px;line-height:1.3}
.weather-temps{font-size:13px;font-variant-numeric:tabular-nums}.weather-temps span{color:#a0a2a6;font-weight:400}
.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));column-gap:18px;row-gap:18px;align-items:stretch}
.metric-card{background:white;border:2px solid var(--card-edge);border-radius:20px;padding:24px 26px;min-height:196px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between;gap:18px;box-shadow:0 3px 14px var(--card-glow);transition:border-color .22s ease,box-shadow .22s ease}
.metric-label{display:flex;align-items:center;gap:10px;font-size:17px;color:#92959a;font-weight:400}
.metric-label-icon{width:23px;height:23px;display:inline-flex;align-items:center;justify-content:center;color:#8e939a;flex:0 0 23px}
.metric-label-icon svg{width:100%;height:100%;display:block}
.metric-value{font-family:'Poppins',sans-serif;font-size:44px;letter-spacing:-1.25px;line-height:1.15;font-weight:400;font-variant-numeric:tabular-nums;white-space:nowrap}
.metric-value small{font-family:'Poppins',sans-serif;font-size:18px;letter-spacing:0;color:#2e3033}
.metric-value sup{font-size:.48em;line-height:0;vertical-align:super;margin-left:1px}
.visibility-value-row{display:flex;align-items:center;gap:14px;min-height:78px}
.visibility-icon{width:48px;height:48px;object-fit:contain;display:block;flex:0 0 48px}
.metric-foot{font-size:15px;color:#777a80;line-height:1.5;min-height:21px}
.metric-foot strong{font-weight:600;color:#222428}
.air-quality-card{min-height:224px}
.aqi-meter{position:relative;width:100%;height:8px;overflow:hidden;border-radius:999px;background:#e5e7eb}
.aqi-meter-fill{height:100%;border-radius:inherit;background-image:repeating-linear-gradient(135deg,rgba(255,255,255,.38) 0 5px,transparent 5px 10px);transition:width .5s ease-out,background-color .3s ease}
.aqi-meter-tick{position:absolute;top:0;bottom:0;width:2px;transform:translateX(-50%);background:#fff;z-index:2}
.aqi-scale{position:relative;height:16px;margin-top:4px;color:#83868b;font-size:10px;font-variant-numeric:tabular-nums}
.aqi-scale span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.aqi-scale span:first-child{transform:none}
.aqi-scale span:last-child{transform:translateX(-100%)}
.air-quality-card .metric-foot strong{font-weight:600}
.metric-card.humidity-card{min-height:214px}
.humidity-ring{position:relative;width:116px;height:116px;flex:0 0 116px;align-self:center;display:grid;place-items:center;border-radius:50%;background:#e9f4eb}
.humidity-ring svg{width:100%;height:100%;display:block}
.humidity-ring .humidity-percent{position:absolute;inset:0;display:grid;place-items:center;font-size:23px;font-weight:500;color:#173c37;font-variant-numeric:tabular-nums}
.uv-card{min-height:250px;padding:16px 20px!important;gap:8px!important;align-items:stretch}
.uv-main{display:flex;align-items:center;justify-content:center;width:100%}
.uv-gauge{width:200px;height:auto;max-width:100%;display:block;overflow:visible}
.uv-gauge .uv-progress{transition:stroke-dashoffset .5s ease,stroke .35s ease}
.uv-gauge .uv-needle{transform-box:view-box;transform-origin:120px 120px;transition:transform .5s ease}
.uv-gauge .uv-tick{font:500 12px 'Poppins',sans-serif;fill:#858990}
.uv-gauge .uv-tick-mark{stroke:#9ca3af;stroke-width:2;stroke-linecap:round}
.uv-gauge .uv-current{font:600 32px 'Poppins',sans-serif;fill:#111}
.sun-times{display:grid;gap:10px}
.sun-time{display:flex;align-items:center;gap:10px;font-variant-numeric:tabular-nums}
.sun-arrow{font-size:24px;line-height:1;font-weight:500;width:25px;text-align:center}
.sun-arrow.up{color:#e8b54a}.sun-arrow.down{color:#6d9ec9}
.sun-time strong{font-size:22px;font-weight:500;color:#202124}
.metric-card.wind-card{min-height:196px;padding:23px 27px}
.wind-card .metric-label{font-size:15px;color:#a1a2a4}
.wind-card .metric-value{font-size:40px;letter-spacing:-1.25px;line-height:1.15;font-weight:400}
.wind-card .metric-value small{font-size:16px;font-weight:400}
.wind-direction{display:flex;align-items:center;gap:11px;color:#17181a;font-size:15px;font-weight:500}
.wind-compass{width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;background:transparent}
.wind-compass img{width:42px;height:42px;display:block;object-fit:contain}
.metric-card.compact{height:320px;min-height:320px;padding:18px 22px;gap:10px}
.metric-card.compact .metric-value{font-size:40px}
.st-key-aqi-insights-grid > div[data-testid="stVerticalBlock"]{gap:22px!important}
.st-key-aqi-insights-row-1 div[data-testid="stHorizontalBlock"],.st-key-aqi-insights-row-2 div[data-testid="stHorizontalBlock"]{gap:22px!important;align-items:stretch}
.st-key-aqi-insights-row-1 div[data-testid="stColumn"],.st-key-aqi-insights-row-2 div[data-testid="stColumn"]{flex:1 1 0!important;width:auto!important;max-width:none!important;min-width:0!important;padding:0!important}
.st-key-aqi-insights-row-1{margin-bottom:20px!important}
.st-key-health-advisory{height:320px;background:white;border:2px solid var(--card-edge);border-radius:20px;box-sizing:border-box;padding:18px 22px;min-height:320px;display:flex;flex-direction:column;justify-content:space-between;gap:12px;box-shadow:0 3px 14px var(--card-glow);transition:border-color .22s ease,box-shadow .22s ease}
.pm25-card{height:320px;min-height:320px!important;padding:14px 22px!important;gap:8px!important;position:relative}
.pm25-card>.air-info{position:absolute;right:20px;top:18px}
.pm25-card>.air-info .air-info-note{left:auto;right:-8px}
.pm25-dial{display:block;width:235px;max-width:100%;height:auto;align-self:center;overflow:visible}
.pm25-dial .pm25-track{fill:none;stroke:#e9eaed;stroke-width:8;stroke-linecap:round}
.pm25-dial .pm25-progress{fill:none;stroke-width:8;stroke-linecap:round;transition:stroke-dashoffset .45s ease,stroke .25s ease}
.pm25-dial .pm25-tick{stroke:#aeb2ba;stroke-width:1.5}
.pm25-dial .pm25-tick-label{font:500 9px 'Poppins',sans-serif;fill:#898d94}
.pm25-dial .pm25-state{font:500 13px 'Poppins',sans-serif;fill:#45484e}
.pm25-dial .pm25-unit{font:500 9px 'Poppins',sans-serif;fill:#8e9298}
.pm25-dial .pm25-value{font:600 25px 'Poppins',sans-serif;fill:#17181a}
.pm25-dial .pm25-needle{stroke-width:2;stroke-linecap:round}
.pm25-dial .pm25-hub{stroke:#fff;stroke-width:2}
.pm25-details{display:flex;align-items:flex-end;justify-content:center;min-height:28px;text-align:center;font-size:11px;line-height:1.4;color:#555960}
.pm25-advice{max-width:300px}
.st-key-health-advisory .stSelectbox label{display:none}
.st-key-health-advisory .stSelectbox{margin:3px 0 0}
.st-key-health-advisory .stSelectbox div[data-baseweb="select"]>div{min-height:30px}
.st-key-health-advisory .stSelectbox div[data-baseweb="select"] *{font-size:11px!important}
.chart-card{background:white;border:2px solid var(--card-edge);border-radius:18px;padding:16px 18px 10px;box-shadow:0 3px 14px var(--card-glow);transition:border-color .22s ease,box-shadow .22s ease}
.forecast-card:hover,.metric-card:hover,.st-key-health-advisory:hover,.chart-card:hover{border-color:#c9e1cc;box-shadow:0 0 0 3px rgba(105,166,116,.055),0 7px 18px rgba(83,139,92,.09)}
.section-note{font-size:12px;color:#96999e;margin-top:-7px;margin-bottom:12px}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:100%;margin-right:7px}
.source-note{font-size:10px;color:#9b9da1;line-height:1.5;margin-top:12px}
.aqi-mark{width:40px;height:40px;border:1px solid #eff0f0;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#fff}
.advice-copy{font-size:12px;line-height:1.5;color:#333539;margin-top:9px}
.insight-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.stPlotlyChart{border-radius:16px}
.today-sidebar-summary{padding:18px 2px 4px}
.today-kicker{font-size:12px;color:#92959a;font-weight:500}
.today-sidebar-title{font-size:27px;line-height:1.3;font-weight:500;letter-spacing:-.6px;margin:12px 0;color:#191a1c}
.today-sidebar-copy{font-size:12px;line-height:1.6;color:#72757b}
.today-city-label{font-size:13px;color:#85888d;margin:0 0 4px}
.window-card{position:relative;box-sizing:border-box;border-radius:18px;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;gap:20px;overflow:visible}
.window-card-featured{min-height:166px;background:linear-gradient(108deg,#e4f4fc 0%,#e5f8f4 58%,#d8f7eb 100%);border:1px solid #94bfd1;box-shadow:0 7px 18px #28597816;color:#15212a}
.window-card-alt{min-height:166px;background:#fff;border:1px solid #e3e7eb;box-shadow:0 5px 13px #202a3512;color:#192027}
.window-card-copy{min-width:0;flex:1}
.window-card .today-kicker{color:#737d86;font-size:11px}
.window-card-featured .today-kicker{display:inline-flex;align-items:center;background:#55a9d2;border-radius:999px;padding:4px 10px;color:#fff;font-size:0;line-height:1;margin-bottom:3px}
.window-card-featured .today-kicker:before{content:"★ Best";font-size:11px;font-weight:600}
.window-time{font-size:28px;line-height:1.2;font-weight:500;letter-spacing:-.6px;margin:7px 0 4px;color:#192027;font-variant-numeric:tabular-nums}
.window-status{font-size:13px;font-weight:600;margin:0 0 8px}
.window-status:before{display:inline-grid;place-items:center;width:16px;height:16px;margin-right:5px;border-radius:50%;background:var(--status-color,currentColor);color:#fff;font-size:11px;line-height:1;vertical-align:-2px}
.window-status.good:before{content:"✓"}.window-status.caution:before{content:"!"}.window-status.avoid:before{content:"×"}
.window-reason{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;font-size:12px;line-height:1.5;color:#35404a}
.window-reason b{font-weight:600;color:#192027;font-variant-numeric:tabular-nums}
.window-reason-item{display:inline-flex;align-items:center;gap:5px}
.window-mini-icon{width:19px;height:19px;display:inline-block;vertical-align:middle}
.window-source{font-size:10px;line-height:1.4;color:#7c858c;margin-top:8px}
.window-card-mark{display:none}
.st-key-today-planner-form{background:linear-gradient(110deg,#eaf6fc 0%,#e3f1f7 100%);border-radius:17px;padding:16px 18px 8px;margin:0 0 24px;border:1px solid #e1eff5}
.st-key-today-planner-form .section-title{color:#245f8e;font-size:20px;font-weight:700;letter-spacing:-.35px;margin:0 0 5px}
.st-key-today-planner-form .section-note{color:#334653;margin:0 0 14px;font-size:12px}
.st-key-today-planner-form label{font-size:12px!important;color:#29343d!important}
.st-key-today-planner-form div[data-baseweb="select"]>div,.st-key-today-planner-form [data-testid="stTimeInput"] input{border-radius:10px!important;background:#fff!important;border-color:#e8e8eb!important}
.st-key-today-planner-form [data-testid="stSlider"]{padding-top:4px}
.probability-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 16px}
.probability-card,.today-mini-card{background:#fff;border:2px solid #c5e3c8;border-radius:18px;padding:17px 19px;min-height:116px;box-sizing:border-box}
.probability-card{box-shadow:0 5px 18px rgba(37,68,88,.11);transition:box-shadow .2s ease,border-color .2s ease}
.probability-card:hover{border-color:#a8d3ae;box-shadow:0 8px 22px rgba(74,131,80,.15)}
.probability-value{font-size:31px;line-height:1.15;letter-spacing:-.7px;font-weight:500;margin:7px 0;color:#191a1c;font-variant-numeric:tabular-nums}
.probability-copy,.today-mini-copy{font-size:12px;line-height:1.55;color:#777a80}
.today-mini-card{height:100%;min-height:170px;display:flex;flex-direction:column;justify-content:space-between;box-sizing:border-box}
.today-mini-card .today-mini-copy{margin:8px 0;overflow-wrap:anywhere}
.today-mini-card .today-why-list{flex:1}
.today-mini-card .window-source{margin-top:auto}
.today-why-list{padding-left:17px;margin:12px 0 0;color:#37393d;font-size:12px;line-height:1.55}
.today-why-list li{margin-bottom:7px}
.today-advice-footer{font-size:11px;color:#878a90;line-height:1.45}
@media(max-width:1100px){.block-container{margin:22px!important}.st-key-dashboard-layout{border-radius:30px}.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-sidebar){border-radius:30px 0 0 30px;flex-basis:26%!important;max-width:26%;padding:26px 20px}.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-main){border-radius:0 30px 30px 0;flex-basis:74%!important;max-width:74%;padding:25px 25px 40px}.forecast-grid{gap:5px}.metric-grid{column-gap:13px;row-gap:14px}.metric-card{padding:20px;min-height:180px}.metric-card.compact{height:290px;min-height:290px;padding:16px 18px}.metric-card.compact .metric-value{font-size:36px}.pm25-card,.st-key-health-advisory{height:290px;min-height:290px;padding:14px 18px}.pm25-dial{width:214px}.st-key-aqi-insights-row-1 div[data-testid="stHorizontalBlock"],.st-key-aqi-insights-row-2 div[data-testid="stHorizontalBlock"]{gap:16px!important}.metric-value{font-size:37px}.metric-label{font-size:15px}.metric-foot{font-size:14px}.uv-card{min-height:235px}.uv-gauge{width:184px}.sun-time strong{font-size:19px}.wind-card .metric-value{font-size:34px}.wind-card .metric-value small{font-size:14px}.wind-card .metric-label{font-size:14px}.wind-direction{font-size:13px}}
@media(max-width:760px){.block-container{margin:0!important}.st-key-dashboard-layout{border-radius:0;min-height:100vh}.st-key-dashboard-layout div[data-testid="stHorizontalBlock"]:has(>div[data-testid="stColumn"] .st-key-dashboard-sidebar){flex-direction:column!important}.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-sidebar){border-right:0;border-bottom:1px solid #d9eaf3;background:linear-gradient(180deg,#e9f5fc 0%,#f5fafe 75%,#fff 100%)}.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-sidebar),.st-key-dashboard-layout div[data-testid="stColumn"]:has(.st-key-dashboard-main){flex:1 1 auto!important;max-width:100%;padding:20px 18px;border-radius:0}.weather-hero{padding-top:12px}.air-illustration{height:118px}.weather-hero .temperature,.aqi-number{font-size:64px}.city-tile{margin-top:18px}.forecast-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.aqi-forecast-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));column-gap:12px;row-gap:12px}.metric-card{min-height:164px;padding:17px}.metric-card.compact{height:280px;min-height:280px;padding:14px}.pm25-card,.st-key-health-advisory{height:280px;min-height:280px;padding:14px}.pm25-dial{width:200px}.metric-card.compact .metric-value{font-size:31px}.st-key-aqi-insights-row-1 div[data-testid="stHorizontalBlock"],.st-key-aqi-insights-row-2 div[data-testid="stHorizontalBlock"]{flex-direction:column!important;gap:12px!important}.metric-value{font-size:33px}.metric-label{font-size:15px}.metric-foot{font-size:14px}.uv-card{min-height:220px}.uv-gauge{width:166px}.sun-time{gap:4px}.sun-time strong{font-size:15px}.sun-time span:last-child{font-size:11px}.sun-arrow{font-size:19px;width:20px}.humidity-ring{width:104px;height:104px;flex-basis:104px}.wind-card .metric-value{font-size:30px}.wind-card .metric-value small{font-size:13px}.section-title{margin-top:22px}}
@media(max-width:480px){.metric-grid{grid-template-columns:1fr}.metric-card{min-height:136px}.forecast-grid,.aqi-forecast-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:900px){.probability-grid{grid-template-columns:1fr}.today-mini-card{min-height:140px}.window-time{font-size:25px}}
.stApp div[data-baseweb="select"]>div,.stApp div[data-baseweb="select"]>div>div,.stApp div[data-baseweb="select"]>div>div>div,.stApp [data-testid="stTimeInput"] input,.stApp [data-baseweb="input"]>div{background-color:#fff!important;background-image:none!important}
.stApp [data-baseweb="select"],.stApp [data-baseweb="select"] *,.stApp [data-baseweb="input"],.stApp [data-testid="stTimeInput"] input{background-color:#fff!important}
.stApp [data-baseweb="popover"] [role="listbox"],.stApp [data-baseweb="popover"] [role="option"],.stApp [data-baseweb="menu"]{background-color:#fff!important}
</style>
"""


def apply_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
