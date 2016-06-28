var key = '12345678'; 

function woosmap_main() {
        var loader = new woosmap.MapsLoader();
        var dataSource = new woosmap.DataSource();
        loader.load(function () {
            var map = new google.maps.Map(woosmap.$('#my-map')[0], {
                center: {lat: 46, lng: 3},
                zoom: 5
            });
            var storeLayer = new woosmap.TiledView(map);
        });

    }
 
document.addEventListener("DOMContentLoaded", function(event) {
   WoosmapLoader.load('1.2', key, woosmap_main);
});