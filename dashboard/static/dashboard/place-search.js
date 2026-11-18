// Buscador de lugares por nombre. Lo usan la página principal y "Mis zonas".
// Pregunta a nuestro servidor (/lugares/?q=...), que a su vez consulta la API de Open-Meteo.
// Uso: ndipPlaceSearch(function (place, label) { ... })  -> se llama cuando la persona elige un resultado.
function ndipPlaceSearch(onPick) {
  var queryInput = document.getElementById('place-query');
  var resultsBox = document.getElementById('place-results');
  var statusBox = document.getElementById('place-status');
  if (!queryInput) return;

  function showResults(places) {
    places.forEach(function (place) {
      var li = document.createElement('li');
      var button = document.createElement('button');
      button.type = 'button';
      button.textContent = place.name;  // textContent evita que un nombre raro se interprete como HTML
      var small = document.createElement('small');
      small.textContent = place.detail;
      button.appendChild(small);
      button.addEventListener('click', function () {
        var label = place.detail ? place.name + ', ' + place.detail : place.name;
        resultsBox.textContent = '';
        statusBox.textContent = '';
        onPick(place, label);
      });
      li.appendChild(button);
      resultsBox.appendChild(li);
    });
  }

  function search() {
    var query = queryInput.value.trim();
    resultsBox.textContent = '';
    if (query.length < 2) { statusBox.textContent = 'Escribe al menos 2 letras.'; return; }
    statusBox.textContent = 'Buscando…';
    fetch(queryInput.dataset.url + '?q=' + encodeURIComponent(query))
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.error) { statusBox.textContent = data.error; return; }
        if (!data.results.length) {
          statusBox.textContent = 'No encontramos ese lugar. Prueba con otro nombre o elige el punto en el mapa.';
          return;
        }
        statusBox.textContent = 'Elige un resultado:';
        showResults(data.results);
      })
      .catch(function () { statusBox.textContent = 'No se pudo buscar en este momento. Elige el punto en el mapa.'; });
  }

  document.getElementById('place-search').addEventListener('click', search);
  queryInput.addEventListener('keydown', function (event) {
    // Enter busca; no debe enviar el formulario que esté alrededor
    if (event.key === 'Enter') { event.preventDefault(); search(); }
  });
}
