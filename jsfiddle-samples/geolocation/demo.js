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

//this function is called when loader finished the API loading
function woosmap_main() {
    var loader = new woosmap.MapsLoader();
    var dataSource = new woosmap.DataSource();
    loader.load(function () {
        var map = new google.maps.Map(woosmap.$('#nearest-store-map')[0], {
            center: {lat: 46, lng: 3},
            zoom: 5
        });
        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});

        var locationProvider = new woosmap.location.LocationProvider();
        var locationProviderMap = new woosmap.location.LocationProvider();
        var zipCodeProvider = new woosmap.ZipCodeProvider();
        var zipCodeWatcher = new woosmap.utils.MVCObject();

        var template = "<b>{{name}}</b><br>{{address.zipcode}} {{address.city}}<br>{{contact.phone}}<br>{{distance}} km";
        var storesInformationTemplateRenderer = new woosmap.TemplateRenderer(template);
        var storesInformationDisplayer = new woosmap.utils.MVCObject();
        storesInformationDisplayer.stores = null;
        storesInformationDisplayer.stores_changed = function () {
            var properties = this.get('stores')[0].properties;
            properties.distance = Math.round(properties.distance / 1000);
            woosmap.$('#store-info').html(storesInformationTemplateRenderer.render(properties));
        };
        storesInformationDisplayer.bindTo('stores', mapView);

        var nearbyStoresSource = new woosmap.location.NearbyStoresSource(dataSource, 1);
        nearbyStoresSource.bindTo('stores', mapView);
        mapView.bindTo('location', locationProviderMap);

        mapView.marker.setOptions({
            draggable: true,
            icon: {url: 'https://developers.woosmap.com/img/markers/geolocated.png'}
        });

        nearbyStoresSource.bindTo('location', locationProviderMap);
        zipCodeProvider.bindTo('location', locationProvider);
        zipCodeWatcher.bindTo('zipcode', zipCodeProvider);

        zipCodeWatcher.zipcode_changed = function () {
            woosmap.$('#geoloc-zipcode-result').html(zipCodeProvider.getZipCode());
        };

        woosmap.$("#geoloc-zipcode-ip").click(function () {
            woosmap.$('#geoloc-zipcode-result').html('looking for ...');
            woosmap.$('#geoloc-zipcode-result').html(zipCodeProvider.getZipCode());
        });
        woosmap.$("#geoloc-zipcode-optin").click(function () {
            locationProvider.askForLocation(navigator.geolocation);
        });

        woosmap.$("#ip-geolocation-button").click(function () {
            locationProviderMap.askForLocation();
        });

        woosmap.$("#html5-geolocation-button").click(function () {
            locationProviderMap.askForLocation(navigator.geolocation);
        });

        /*----------   DistanceProvider  --------------*/
        var template = woosmap.$('#closest-store-template').html();
        var anotherLocationProvider = new woosmap.location.LocationProvider();
        var anotherNearbyStoresSource = new woosmap.location.NearbyStoresSource(dataSource, 10);
        var distanceProvider = new woosmap.location.DistanceProvider();
        var closestStoreTemplateRenderer = new woosmap.TemplateRenderer(template);
        var closestStoreDisplayer = new woosmap.utils.MVCObject();
        closestStoreDisplayer.stores = null;
        closestStoreDisplayer.stores_changed = function () {
            distanceProvider.updateStoresDistanceWithGoogle(this.get('stores'), function (updated_stores) {
                var $storesDiv = woosmap.$('#closest-store-info');
                var store_properties = updated_stores[0].properties;
                store_properties.distance = store_properties.distance / 1000;
                store_properties.duration = Math.round(store_properties.duration / 60);
                $storesDiv.html(closestStoreTemplateRenderer.render(store_properties));
                $storesDiv.show();
            }, 'duration');
        };


        closestStoreDisplayer.bindTo('stores', anotherNearbyStoresSource);
        anotherNearbyStoresSource.bindTo('location', anotherLocationProvider);
        distanceProvider.bindTo('location', anotherLocationProvider);
        woosmap.$('#update-stores-distance').click(function () {
            anotherLocationProvider.askForLocation(navigator.geolocation);
        });


    });
}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('latest', projectKey, woosmap_main);
});
