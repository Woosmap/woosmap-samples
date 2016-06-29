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

/*----- Init and display a Map with a TiledLayer-----*/
function woosmap_main() {
    var loader = new woosmap.MapsLoader();
    var dataSource = new woosmap.DataSource();
    loader.load(function () {
        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {lat: 46, lng: 3},
            zoom: 5
        });
        var template = '<div id="info-item" class="info-item"><a class="title">' +
            '{{name}}<br><small class="quiet">{{address.city}}</small></a>' +
            '<div>{{address.lines}} {{address.city}} {{address.zip}}</div>' +
            '<div>Tel : <a href="tel:{{contact.phone}}">{{contact.phone}}</a></div></div>';

        var renderer = new woosmap.TemplateRenderer(template);
        var win = new woosmap.LocatorWindow(map, renderer);

        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});
        win.bindTo('selectedStore', mapView);
    });

}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('1.2', projectKey, woosmap_main);
});
