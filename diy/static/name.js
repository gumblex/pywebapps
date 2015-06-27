function LoadJSON(fc) {
    var xmlhttp;
    if (window.XMLHttpRequest) {
        // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp = new XMLHttpRequest();
    } else {
        // code for IE6, IE5
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange = function() {
        if (xmlhttp.readyState == XMLHttpRequest.DONE) {
            FillInResult(xmlhttp.responseText, xmlhttp.status);
        }
    }
    xmlhttp.open("GET", "?c=" + encodeURIComponent(fc), true);
    xmlhttp.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xmlhttp.send();
}

function FillInResult(result, code) {
    var d = JSON.parse(result);
    if (d['s'].length) {
        document.getElementById("surnames").className = '';
        document.getElementById("snlist").textContent = d['s'].join(', ');
    } else {
        document.getElementById("surnames").className = 'hid';
    }
    document.getElementById("nlist").innerHTML = d['n'].join(', ');
}

function MakeRequest() {
    LoadJSON(document.getElementById("fc").value);
    return false;
}

function FillInExample() {
    document.getElementById("fc").value = this.textContent;
    MakeRequest();
    return false;
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById("formgetname").onsubmit = MakeRequest;
    var as = document.getElementById("example").getElementsByTagName('a');
    var aslen = as.length, i = 0;
    for (i = 0; i < aslen; i++) {
        as[i].href = '#';
        as[i].onclick = FillInExample;
    }
});
