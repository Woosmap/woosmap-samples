var key = '12345678'; 

function woosmap_main() {
        var loader = new woosmap.MapsLoader();
        var dataSource = new woosmap.DataSource();
        loader.load(function () {
            var map = new google.maps.Map(woosmap.$('#my-map')[0]);
            var storeLayer = new woosmap.TiledView(map);
        });

    }
 
if (window.attachEvent)
    window.attachEvent('onload', function () {WoosmapLoader.load('1.2', key, woosmap_main)});
else
    window.addEventListener('load', WoosmapLoader.load('1.2', key, woosmap_main), false);