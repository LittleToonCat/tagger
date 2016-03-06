
var gameInfo = {
  'server_url' : 
  'g://gameserver.ddrose.com:443',
  //'g://localhost:4430',
  'poster_urls' : []
};

function OnPythonLoad() {
}

function OnLoad() {
}

function ChangePoster() {
  var tagger = document.getElementById('tagger');
  tagger.main.changePoster();
}
