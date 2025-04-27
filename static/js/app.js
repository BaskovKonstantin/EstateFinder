/* global $, L */
$(function () {

  //------------------------------------------------------------------
  //  Leaflet карта  (ч/б)
  //------------------------------------------------------------------
  const map = L.map('map').setView([59.93, 30.33], 11);
  L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    { attribution: '© OpenStreetMap & Carto', maxZoom: 19 }
  ).addTo(map);
  let marker;   // активный маркер

  //------------------------------------------------------------------
  //  DataTable
  //------------------------------------------------------------------
  let dt;

  const DEFAULT_COLS = new Set([
    'address',
    'price_score',
    'location_score',
    'composite_score'
  ]);

  //------------------------------------------------------------------
  //  loader helpers
  //------------------------------------------------------------------
  const showLoader = state => $('#loader').css('display', state ? 'flex' : 'none');

  //------------------------------------------------------------------
  //  submit формы
  //------------------------------------------------------------------
  $('#search-form').on('submit', async e => {
    e.preventDefault();
    $('#btn-search').prop('disabled', true).text('Жду…');
    showLoader(true);

    try {
      const qs = $(e.target).serialize();
      const res = await fetch('/search?' + qs);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      $('#cnt').text(data.count);

      //--------------------------------------------------------------
      //  формируем колонки
      //--------------------------------------------------------------
      const keys = Object.keys(data.estates[0]);        // уже без nearby_…
      const cols = keys.map(k => ({
        title: k,
        data:  k,
        visible: DEFAULT_COLS.has(k)
      }));

      // пересоздаём таблицу
      if (dt) dt.destroy();
      $('#thead-row').empty().append(
        cols.map(c => $('<th>').text(c.title))
      );

      dt = $('#result-table').DataTable({
        dom: 'Bfrtip',
        buttons: [{ extend: 'colvis', text: 'Скрыть / показать столбцы' }],
        data: data.estates,
        columns: cols,
        pageLength: 25,
        scrollX: true
      });

      //--------------------------------------------------------------
      //  клик по строке -> Leaflet
      //--------------------------------------------------------------
      $('#result-table tbody').off('click').on('click', 'tr', function () {
        const row = dt.row(this).data();
        if (!row || !row.coords) return;
        const [lat, lon] = row.coords;

        if (marker) map.removeLayer(marker);
        marker = L.marker([lat, lon])
                  .addTo(map).bindPopup(row.address || row.id).openPopup();
        map.setView([lat, lon], 16);
      });

    } catch (err) {
      console.error(err);
      alert('Ошибка: ' + err.message);
    } finally {
      $('#btn-search').prop('disabled', false).text('Поиск');
      showLoader(false);
    }
  });
});
