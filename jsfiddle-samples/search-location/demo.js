var projectKey = '12345678';
var markersStyle = {
    rules: [
        {
            type: 'drive',
            icon: {url: 'https://images.woosmap.com/marker_drive.svg', scaledSize: {width: 36, height: 48}},
            selectedIcon: {url: 'https://images.woosmap.com/marker_drive_selected.svg', scaledSize: {width: 46, height: 60}},
            numberedIcon: {url: 'https://images.woosmap.com/marker_drive_selected.svg', scaledSize: {width: 46, height: 60}}
        }
    ],
    default: {
        icon: {url: 'https://images.woosmap.com/marker_default.svg', scaledSize: {width: 36, height: 48}},
        selectedIcon: {url: 'https://images.woosmap.com/marker_selected.svg', scaledSize: {width: 46, height: 60}}
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
    var loader = new woosmap.MapsLoader();
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
        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {lat: 46, lng: 3},
            zoom: 5
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

        registerDraggableMarker(mapView);

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
    WoosmapLoader.load('latest', projectKey, woosmap_main);
});