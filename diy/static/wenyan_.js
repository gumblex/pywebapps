var languncertain = true, ilang = 'auto', originput = '', notchanged = true;
function escapeHtml(text) {
    var map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'};
    return text.replace(/[&<>"']/g, function(m) {return map[m];});
}
function Checktxttype(s) {
    var cscore = 0, mscore = 0, o = 0;
    var i = s.length;
    while (i--) {
        o = s.charCodeAt(i);
        if (0x4E00 <= o && o < 0x9FCD) {
            cscore -= zhcmodel.charCodeAt(o-0x4E00);
            mscore -= zhmmodel.charCodeAt(o-0x4E00);
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
    var kc = 34, bc = 10938, km = 21, bm = 3516; ////
    var ilen = document.getElementById("tinput").value.length;
    PBar.style["transition-duration"] = (ilang === 'm2c' ? km * ilen + bm : kc * ilen + bc) + "ms";
    PBar.style["width"] = origwid + "px";
}
function TypeHint() {
    if (languncertain) {
        ilang = Checktxttype(document.getElementById("tinput").value);
        if (ilang !== 'auto') {
            document.getElementById("hilang").value = ilang;
            document.getElementById("ctrlauto").firstChild.nodeValue = (ilang === 'c2m' ? c2mtxt : m2ctxt);
            document.getElementById("ctrlchange").style.display = "inline-block";
        }
    }
    document.getElementById("ctrlsubmit").disabled = (document.getElementById("tinput").value.length > 2000);
}
function Highlight() {
    if (document.getElementById("tinput").value === originput) {
        var key = parseInt(this.id.slice(1));
        var al = talign[key];
        var anum = al.length;
        var res = '', i = 0, lastch = 0;
        for (i = 0; i < anum; i++) {
            res += (escapeHtml(originput.slice(lastch, al[i][0])) + '<span class="hl">' +
                    escapeHtml(originput.slice(al[i][0], al[i][1])) + '</span>');
            lastch = al[i][1];
        }
        res += escapeHtml(originput.slice(lastch));
        document.getElementById("hl-input").innerHTML = res;
        document.getElementById("hl-input").style.display = "block";
        this.className = 'hl';
    }
}
function Restore() {
    document.getElementById("hl-input").style.display = "none";
    this.className = '';
}
function SelWord() {
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(this);
    selection.removeAllRanges();
    selection.addRange(range);
}
function AttachHlEvents() {
    var spans = document.getElementById("toutput").getElementsByTagName('span');
    var spanslen = spans.length, i = 0;
    for (i = 0; i < spanslen; i++) {
        spans[i].id = 'w' + i;
        spans[i].addEventListener('mouseover', Highlight);
        spans[i].addEventListener('mouseout', Restore);
        spans[i].addEventListener('blur', Restore);
        spans[i].addEventListener('contextmenu', SelWord);
    }
}
document.addEventListener('DOMContentLoaded', function() {
    originput = document.getElementById("tinput").value;
    document.getElementById("hl-input").textContent = originput;
    document.getElementById("tinput").onchange = TypeHint;
    document.getElementById("ctrlchange").onclick = function() {
        languncertain = false;
        ilang = (ilang === 'c2m' ? 'm2c' : 'c2m');
        document.getElementById("hilang").value = ilang;
        document.getElementById("ctrlauto").firstChild.nodeValue = (ilang === 'c2m' ? c2mtxt : m2ctxt);
        return false;
    }
    document.getElementById("translateform").onsubmit = PBRun;
    AutoGrow(document.getElementById('tinput'));
    AttachHlEvents();
    TypeHint();
});
