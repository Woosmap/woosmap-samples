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
    color: 'rgba(0, 0, 0, 1)',
    size: 11,
    minSize: 6,
    typeRules: [{
        type: 'auchan',
        color: '#aa4d55'
    }, {
        type: 'drive',
        color: '#82a859'
    }]
};

/*----- Handle store selection -----*/
function registerLocationClickEvent(mapView) {
    var selectedStoreObserver = new woosmap.utils.MVCObject();
    selectedStoreObserver.selectedStore = null;
    selectedStoreObserver.selectedStore_changed = function () {
        var selectedStore = this.get('selectedStore');
        alert(selectedStore.properties.name);
    };
    selectedStoreObserver.bindTo('selectedStore', mapView);
}

/*----- Store by Location, with distance -----*/
function registerNearbyClickEvent(mapView, dataSource) {
    var MAX_STORE = 10;
    var MAX_DISTANCE_FROM_LOCATION = 150000; //150km
    var nearbyStoreSource = new woosmap.location.NearbyStoresSource(dataSource, MAX_STORE, MAX_DISTANCE_FROM_LOCATION);
    nearbyStoreSource.bindTo('location', mapView);
    nearbyStoreSource.bindTo('stores', mapView);

    woosmap.$('#go-to-paris').on('click', function () {
        mapView.set('location', {
            lat: 48.85,
            lng: 2.27
        });
    });
}

function registerDraggableMarker(mapView) {
    mapView.marker.setOptions({
        draggable: true,
        icon: {url: 'https://developers.woosmap.com/img/markers/geolocated.png'}
    });
}
/*----- Init and display a Map with a TiledLayer-----*/
function woosmap_main() {
    var loader = new woosmap.MapsLoader();
    var dataSource = new woosmap.DataSource();
    loader.load(function () {
        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {lat: 46, lng: 3},
            zoom: 5
        });
        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});
        registerNearbyClickEvent(mapView, dataSource);
        registerLocationClickEvent(mapView);
        registerDraggableMarker(mapView);
    });

}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('1.2', projectKey, woosmap_main);
});
