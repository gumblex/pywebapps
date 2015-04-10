var languncertain = true, detectedlang = 'auto';
function Checktxttype(s) {
    var cscore = 0, mscore = 0, o = 0;
    var i = s.length;
    while (i--) {
        o = s.charCodeAt(i);
        if (0x4E00 <= o && o < 0x9FCD) {
            cscore -= 126-zhcmodel.charCodeAt(o-0x4E00);
            mscore -= 126-zhmmodel.charCodeAt(o-0x4E00);
        }
    }
    if (cscore > mscore) {return 'c2m'}
    else if (cscore < mscore) {return 'm2c'}
    else {return 'auto'}
}
function AutoGrow(oField) {
    if (oField.scrollHeight > oField.clientHeight) {
        oField.style.height = oField.scrollHeight + oField.clientTop * 2 + 1 + "px";
    }
}
function PBRun() {
    TypeHint();
    var PBar = document.getElementById('progressbar');
    var origwid = document.getElementById('toutput').offsetWidth;
    var k = 24, b = 3347; ////
    PBar.style["transition-duration"] = k * document.getElementById("tinput").value.length + b + "ms";
    PBar.style["width"] = origwid + "px";
}
function TypeHint() {
    if (languncertain) {
        detectedlang = Checktxttype(document.getElementById("tinput").value);
        if (detectedlang !== 'auto') {
            document.getElementById("hilang").value = detectedlang;
            document.getElementById("ctrlauto").textContent = (detectedlang === 'c2m' ? c2mtxt : m2ctxt);
            document.getElementById("ctrlchange").style.display = "inline-block";
        }
    }
}
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById("tinput").onchange = TypeHint;
    document.getElementById("ctrlchange").onclick = function() {
        languncertain = false;
        detectedlang = (detectedlang === 'c2m' ? 'm2c' : 'c2m');
        document.getElementById("hilang").value = detectedlang;
        document.getElementById("ctrlauto").innerText = (detectedlang === 'c2m' ? c2mtxt : m2ctxt);
        return false;
    }
    document.getElementById("translateform").onsubmit = PBRun;
    AutoGrow(document.getElementById('tinput'));
    TypeHint();
});
