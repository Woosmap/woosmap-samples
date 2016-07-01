var projectKey = '12345678';
var markersStyle = {
    rules: [
        {
            type: 'drive',
            icon: {url: 'https://developers.woosmap.com/img/markers/marker_drive.png'},
            selectedIcon: {url: 'https://developers.woosmap.com/img/markers/marker_selected.png'}
        }
    ],
    default: {
        icon: {url: 'https://developers.woosmap.com/img/markers/marker_default.png'},
        selectedIcon: {url: 'https://developers.woosmap.com/img/markers/marker_selected.png'}
    }
};
var tilesStyle = {
    color: '#383838',
    size: 11,
    minSize: 6,
    typeRules: [{
        type: 'drive',
        color: '#82a859'
    }]
};

function registerDraggableMarker(mapView) {
    mapView.marker.setOptions({
        draggable: true,
        icon: {url: 'https://developers.woosmap.com/img/markers/geolocated.png'}
    });
}

/*----- Init and display a Map with a TiledLayer-----*/
function woosmap_main() {
    var self = this;
    var loader = new woosmap.MapsLoader("", ['places']);
    var dataSource = new woosmap.DataSource();
    loader.load(function () {
        var tableview = new woosmap.ui.TableView({
            cell_store: '<div id="item" class="item"><a class="title">' +
            '{{name}}<br><small class="quiet">{{address.city}}</small></a>' +
            '<div>{{address.lines}} {{address.city}} {{address.zip}}</div></div>',
            cell_place: '<div id="item" class="item"><a class="title">{{description}}</a></div>'
        });
        var geocoder = new woosmap.location.GeocoderSearchSource();
        var searchview = new woosmap.ui.SearchView(woosmap.$('#search_template').text());
        var nearbyStoresSource = new woosmap.location.NearbyStoresSource(dataSource, 5);

        nearbyStoresSource.bindTo('location', geocoder, 'location', false);
        tableview.bindTo('stores', nearbyStoresSource);
        geocoder.bindTo('query', searchview, 'query', false);

        var listings = woosmap.$('#listings');
        var sidebar = woosmap.$('.sidebar');

        sidebar.prepend(searchview.getContainer());
        listings.append(tableview.getContainer());

        self.tableview = tableview;
        var defaultStores = null;
        var map = new google.maps.Map(woosmap.$('#map')[0], {
            center: {lat: 42, lng: 3},
            zoom: 7,
            scrollwheel: false,
            draggable: false
        });

        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});
        mapView.bindTo('stores', tableview, 'stores', false);
        mapView.bindTo('selectedStore', tableview, 'selectedStore', false);
        mapView.bindTo('location', geocoder);
        mapView.delegate = {
            'didLocationMarkerDragEnd': function () {
                searchview.$searchInput.val('');
            }
        };


        mapView.marker.setOptions({
            draggable: true
        });

        searchview.delegate = {
            didClearSearch: function () {
                tableview.set('stores', defaultStores);
                mapView.set('selectedStore', null);
                mapView.set('location', {})
            }
        };

    });

}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('1.2', projectKey, woosmap_main);
});