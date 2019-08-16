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
        icon: {url: 'https://dimages.woosmap.com/marker_default.svg', scaledSize: {width: 36, height: 48}},
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
        icon: {
            url: 'https://developers.woosmap.com/img/markers/geolocated.png'
        }
    });
}

/*----- Init and display a Map with a TiledLayer-----*/
function woosmap_main() {
    var self = this;
    var loader = new woosmap.MapsLoader("", ['places']);
    var dataSource = new woosmap.DataSource();
    loader.load(function () {

        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {
                lat: 46,
                lng: 3
            },
            zoom: 5
        });

        var mapView = new woosmap.TiledView(map, {
            style: markersStyle,
            tileStyle: tilesStyle
        });

        var searchview = new woosmap.ui.SearchView(woosmap.$('#search_template').text());

        var initialSearchTextOptions = {
            name: woosmap.search.SearchQuery.OR,
            city: woosmap.search.SearchQuery.OR
        };
        var searchQuery = new woosmap.search.SearchQuery(initialSearchTextOptions);

        var searchTextOptionsRenderer = new woosmap.TemplateRenderer(woosmap.$("#text-search-options-template").html());
        var tagsRenderer = new woosmap.TemplateRenderer(woosmap.$("#tags-selector-template").html());
        var typesRenderer = new woosmap.TemplateRenderer(woosmap.$("#types-selector-template").html());
        var attributeSearchContainer = woosmap.$('<div class="attributes-search-container">');
        attributeSearchContainer.append(searchview.getContainer());
        attributeSearchContainer.append(searchTextOptionsRenderer.render());
        attributeSearchContainer.append(tagsRenderer.render());
        attributeSearchContainer.append(typesRenderer.render());
        var sidebar = woosmap.$('.sidebar');
        sidebar.prepend(attributeSearchContainer);

        function typeChanged() {
            searchQuery.types = [];
            woosmap.$.each(woosmap.$('.woosmap-available-type:checked'), function (index, object) {
                searchQuery.addTypeFilter(woosmap.$(object).val(), woosmap.search.SearchQuery.AND);
            });
            mapView.setSearchQuery(searchQuery);
        }

        function tagChanged() {
            searchQuery.tags = [];
            woosmap.$.each(woosmap.$('.woosmap-available-tag:checked'), function (index, object) {
                searchQuery.addTagFilter(woosmap.$(object).val(), woosmap.search.SearchQuery.AND);
            });
            mapView.setSearchQuery(searchQuery);
        }

        woosmap.$('.woosmap-available-tag').click(function () {
            tagChanged();
        });

        woosmap.$('.woosmap-available-type').click(function () {
            typeChanged();
        });

        woosmap.$('.woosmap-text-search-param').click(function () {
            if (this.checked) {
                searchQuery.addQueryOption(woosmap.$(this).val(), woosmap.search.SearchQuery.OR)
            } else {
                searchQuery.removeQueryOption(woosmap.$(this).val())
            }
            mapView.setSearchQuery(searchQuery);
        });

        woosmap.$('.search_input').on("change paste keyup", function () {
            searchQuery.setQuery(woosmap.$(this).val());
            mapView.setSearchQuery(searchQuery);
        });

        searchview.delegate = {
            didClearSearch: function () {
                searchQuery.setQuery('');
                mapView.setSearchQuery(searchQuery);
            }
        };
    });

}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('1.2', projectKey, woosmap_main);
});

