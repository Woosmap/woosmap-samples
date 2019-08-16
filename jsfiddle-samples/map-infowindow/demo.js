var projectKey = '12345678';
var markersStyle = {
    rules: [
        {
            type: 'drive',
            icon: {url: 'https://images.woosmap.com/marker_drive.svg', scaledSize: {width: 36, height: 48}},
            selectedIcon: {url: 'https://images.woosmap.com/marker_drive_selected.svg', scaledSize: {width: 46, height: 60}}
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
