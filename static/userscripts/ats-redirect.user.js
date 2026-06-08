// ==UserScript==
// @name        ATS redirect
// @namespace   Blorptopia
// @version     1.0.0
//
// @match       https://www.finn.no/job/ad/*
// @match       https://arbeidsplassen.nav.no/*
// @grant       GM_registerMenuCommand
// @grant       GM_getValue
//
// @author      -
// @description
// ==/UserScript==

const ATS_BASE_URL = GM_getValue("base_url") ?? "http://localhost:8000";

GM_registerMenuCommand("Open in ATS", () => {
  const url = new URL(ATS_BASE_URL);
  url.pathname = "/applications/find";
  url.searchParams.set("id_or_url", location.href);
  location.href = url.toString();
});

