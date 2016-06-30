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

        /******** usefull function ********/
        function closeRouteContainer() {
            woosmap.$('.route-summary-upper-panel').addClass('hide');
            woosmap.$('.route-summary-lower-panel').hide();
            woosmap.$('.woosmap-route-details').hide();
            woosmap.$('.woosmap-route-info-container').addClass('hide');
        }

        function displayRouteContainer(container) {
            var $container = woosmap.$(container);
            $container.find('.route-summary-lower-panel').show();
            $container.find('.woosmap-route-details').show();
            $container.find('.woosmap-route-info-container').removeClass('hide');
            $container.find('.route-summary-upper-panel').removeClass('hide');
        }

        function makeMarker(position, icon, title) {
            directionsMarkers.push(new google.maps.Marker({
                position: position,
                map: map,
                icon: icon,
                title: title
            }));
        }

        function cleanMarker() {
            woosmap.$.each(directionsMarkers, function (index, marker) {
                marker.setMap(null);
            });
            directionsMarkers = [];
        }

        /*********************************/

        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {lat: 44, lng: 4},
            zoom: 7,
            disableDefaultUI: true
        });

        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});

        dataSource.getAllStores(function (geojson) {
            woosmap.$("#inputs").show();
            mapView.set('stores', geojson.features);
        });

        /**** directions renderers options ****/
        var newPolylineOption = {
            strokeColor: '#1badee',
            strokeOpacity: 1.0,
            strokeWeight: 4,
            icons: ['https://developers.woosmap.com/img/markers/marker.png']
        };

        // Start/Finish icons
        var icons = {
            start: 'https://developers.woosmap.com/img/markers/start.png',
            end: 'https://developers.woosmap.com/img/markers/end.png'
        };
        var directionRendererOptions = {
            suppressMarkers: true,
            suppressInfoWindows: true,
            polylineOptions: newPolylineOption
        };

        var googleDirectionsRequestOptions = {
            provideRouteAlternatives: true,
            durationInTraffic: true
        };
        /***************************************/

        var directionsMarkers = [];
        var navigatorGeolocation = new woosmap.location.LocationProvider();
        var travelModeSelector = new woosmap.ui.TravelModeSelector(woosmap.$('#travel-mode-selector-template').html());
        var originDestinationInput = new woosmap.ui.OriginDestinationInput(woosmap.$('#directions-origin-destination-template').html(), {'geolocText': 'Ma Position'});
        var directionsProvider = new woosmap.location.DirectionsProvider(directionRendererOptions, googleDirectionsRequestOptions);
        var mailView = new woosmap.ui.MailView(woosmap.$('#directions-mail-input-template').html());
        var locationProvider = new woosmap.location.LocationProvider();
        var store_id = location.search.split('store_id=')[1] ? location.search.split('store_id=')[1] : '';
        var directionsRestorer = new woosmap.utils.MVCObject();
        directionsRestorer.location = null;
        directionsRestorer.location_changed = function () {
            var self = this;
            if (store_id) {
                dataSource.getStoreById(store_id, function (data) {
                    originDestinationInput.set('selectedStore', data);
                    originDestinationInput.set('location', self.get('location'));
                });
            }
        };

        var directionsResultsDisplayer = new woosmap.ui.DirectionsResultsDisplayer(map, woosmap.$('#directions-summary-template').html(),
            function () {
                //this function is called when directionResultsDisplayer finished to display renderers
                directionsResultsDisplayer.displayRouteOnMap(0);
                directionsResultsDisplayer.displayRouteSteps(0);
                woosmap.$("#directions").show();
                var computedDirections = directionsResultsDisplayer.get("directionsRenderers")[0].getDirections();
                var leg = computedDirections.routes[0].legs[0];
                cleanMarker();
                makeMarker(leg.start_location, icons.start, "Start");
                makeMarker(leg.end_location, icons.end, 'End');

                closeRouteContainer();
                displayRouteContainer(woosmap.$('.woosmap-route-container')[0]);

                woosmap.$('.woosmap-route-container').click(function () {
                    closeRouteContainer();
                    displayRouteContainer(this);
                    directionsResultsDisplayer.cleanMapFromRoutes();
                    directionsResultsDisplayer.cleanRouteSteps();
                    directionsResultsDisplayer.displayRouteOnMap(woosmap.$(this).find('.woosmap-show-steps').data('renderer-index'));
                    directionsResultsDisplayer.displayRouteSteps(woosmap.$(this).find('.woosmap-show-steps').data('renderer-index'));
                });

                woosmap.$('.woosmap-route-details').click(function () {
                    woosmap.$('#instructions').show();
                    woosmap.$('#routes').hide();
                    woosmap.$('#inputs').hide();
                    woosmap.$('#instructions-mail').hide();
                    woosmap.$('#directions').css('top', '5px');
                    woosmap.$('#directions').css('bottom', '5px');
                });

                woosmap.$('#close-instructions-button').click(function () {
                    woosmap.$('#instructions').hide();
                    woosmap.$('#routes').show();
                    woosmap.$('#inputs').show();
                    woosmap.$('#instructions-mail').show();
                    woosmap.$('#directions').css('top', '135px');
                    woosmap.$('#directions').css('bottom', '');
                });
            }
        );

        originDestinationInput.bindTo('selectedStore', mapView);
        directionsProvider.bindTo('selectedTravelMode', travelModeSelector);
        directionsProvider.bindTo('originDestination', originDestinationInput);
        directionsResultsDisplayer.bindTo('directionsSummaries', directionsProvider);
        directionsResultsDisplayer.bindTo('directionsRenderers', directionsProvider);
        directionsResultsDisplayer.bindTo('directionsLink', directionsProvider);
        originDestinationInput.bindTo('location', navigatorGeolocation);
        mailView.bindTo('selectedStore', mapView);
        directionsRestorer.bindTo('location', locationProvider);

        function _update_mail_status(text, color) {
            var $mailStatusDiv = woosmap.$('#mail-status');
            $mailStatusDiv.html(text).css('color', color);
            $mailStatusDiv.show();
            setTimeout(function () {
                $mailStatusDiv.hide(1000);
            }, 3000);
        }

        mailView.delegate = {
            mailSent: function () {
                _update_mail_status('Email envoyé', 'green');
                woosmap.$('.woosmap-mail-input').val("");
            },
            mailError: function () {
                _update_mail_status('Erreur', 'red');
            }
            ,
            mailSending: function () {
                _update_mail_status('Envoi en cours', '#1badee');
            }
        };

        woosmap.$('#map-container').append(originDestinationInput.getODContainer());
        woosmap.$('#routes').append(directionsResultsDisplayer.getRoutesContainer());
        woosmap.$('#instructions-steps').append(directionsResultsDisplayer.getStepsContainer());
        woosmap.$('#directions-travel-mode-selector').append(travelModeSelector.getSelectorContainer());

        woosmap.$('#instructions-mail').empty().append(mailView.getContainer());

        if (new woosmap.DeviceDetector().getDeviceType() == 'mobile') {
            woosmap.$('.woosmap-mail-container').hide();
        } else {
            woosmap.$('.woosmap-mobile-form-menu').click(function () {
                woosmap.$('.woosmap-mobile-form').toggle();
            });
        }

        woosmap.$(".woosmap-directions-origin .woosmap-close-icon").click(function () {
            woosmap.$("#woosmap-directions-origin-input").val('');
        });

        woosmap.$(".woosmap-directions-destination .woosmap-close-icon").click(function () {
            woosmap.$("#woosmap-directions-destination-input").val('');
        });

        woosmap.$('#directions-travel-mode-selector .woosmap-travel-mode-option').click(function () {
            woosmap.$('#directions-travel-mode-selector .woosmap-travel-mode-option').removeClass('selected');
            woosmap.$(this).addClass('selected');
        });

        woosmap.$('.geolocation-button').click(function () {
            navigatorGeolocation.askForLocation(navigator.geolocation);
        });

        google.maps.event.addListener(map, 'click', function (event) {
            originDestinationInput.set('location', {'lat': event.latLng.lat(), 'lng': event.latLng.lng()});
        });

        if (store_id) {
            locationProvider.askForLocation(navigator.geolocation);
        }
    });
}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('latest', projectKey, woosmap_main);
});