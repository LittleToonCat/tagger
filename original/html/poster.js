function getArgs() { 
  var args = new Object(); 
  var query = location.search.substring(1); 
  var pairs = query.split("&");

  for (var i = 0; i < pairs.length; i++) { 
    var pos = pairs[i].indexOf('='); 
    if (pos == -1) {
      continue; 
    }

    var argname = pairs[i].substring(0,pos); 
    var value = pairs[i].substring(pos+1); 
    value = decodeURIComponent(value); 
    args[argname] = value;
  } 
  return args;
}

function OnLoad() {
  var args = getArgs();
  var form = document.getElementById('posterForm');

  if (args['success']) {
    // If we've successfully sent the data, reveal the "sent" text.
    document.getElementById('sent').style.display = 'block';

  } else {
    // Otherwise, reveal the form.
    form.style.display = 'block';
    document.getElementById('playerId').value = args['playerId'];

    var nextUrl = location.href.substr(0, location.href.length - location.search.length);
    document.getElementById('nextUrl').value = nextUrl;
  }
}

function OnSubmit() {
  var form = document.getElementById('posterForm');
  form.style.display = 'none';
  document.getElementById('uploading').style.display = 'block';
  return true;
}
