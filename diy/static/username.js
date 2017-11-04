function LoadJSON() {
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
    xmlhttp.open("GET", "?f=json", true);
    xmlhttp.send();
}

function FillInResult(result, code) {
    var d = JSON.parse(result);
    var result = '';
    var i = d['usernames'].length;
    while (i --> 0) {
        result += '<li>' + d['usernames'][i] + '</li>'
    }
    document.getElementById("usernames").innerHTML = result;
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById("btnrefresh").onclick = LoadJSON;
});
