var languncertain = false;
function AutoGrow(oField) {
if (oField.scrollHeight > oField.clientHeight) {
oField.style.height = oField.scrollHeight + oField.clientTop*2 + 1 + "px";
}}
function PBRun() {
var PBar = document.getElementById('progressbar');
var origwid = document.getElementById('toutput').offsetWidth;
var k = 24, b = 3347; ////
PBar.style["transition-duration"] = k * document.getElementById("tinput").value.length + b + "ms";
PBar.style["width"] = origwid + "px";
}
document.addEventListener('DOMContentLoaded', function() {
if (languncertain) {
document.getElementById("changedir").onclick = function() {
document.getElementById("hidden-lang").value = languncertain;
document.getElementById("translateform").submit();
return false;
}
}
AutoGrow(document.getElementById('tinput'));
document.getElementById("translateform").onsubmit = PBRun;
});