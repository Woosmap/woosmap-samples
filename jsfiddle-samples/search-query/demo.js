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
    var self = this;
    var loader = new woosmap.MapsLoader("", ['places']);
    var dataSource = new woosmap.DataSource();
    loader.load(function () {

        var map = new google.maps.Map(woosmap.$('#my-map')[0], {
            center: {lat: 46, lng: 3},
            zoom: 5
        });

        var mapView = new woosmap.TiledView(map, {style: markersStyle, tileStyle: tilesStyle});

        var tableview = new woosmap.ui.TableView({
            cell_store: woosmap.$("#store-row-template").html()
        });
        mapView.bindTo('stores', tableview);
        mapView.bindTo('selectedStore', tableview, 'selectedStore', false);

        var searchview = new woosmap.ui.SearchView(woosmap.$('#search_template').text());

        var initialSearchTextOptions = {
            name: woosmap.DataSearchSource.OR,
            city: woosmap.DataSearchSource.OR
        };
        var dataSearchSource = new woosmap.DataSearchSource(dataSource, initialSearchTextOptions);
        dataSearchSource.bindTo('autocomplete_query', searchview, 'autocomplete_query', false);
        tableview.bindTo('stores', dataSearchSource);

        var listings = woosmap.$('#listings');
        listings.append(tableview.getContainer());
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

        function typeOrTagChanged(typeOrTag) {
            var newFilters = [];
            woosmap.$.each(woosmap.$('.woosmap-available-' + typeOrTag + ':checked'), function (index, object) {
                newFilters.push({
                    value: woosmap.$(object).val(),
                    operator: woosmap.DataSearchSource.AND
                });
            });
            dataSearchSource.updateSearchQueryAndSearch(typeOrTag + 's', newFilters);
        }

        woosmap.$('.woosmap-available-tag').click(function () {
            typeOrTagChanged('tag');
        });

        woosmap.$('.woosmap-available-type').click(function () {
            typeOrTagChanged('type');
        });

        woosmap.$('.woosmap-text-search-param').click(function () {
            if (this.checked) {
                dataSearchSource.addFieldToSearchTextOptions(woosmap.$(this).val(), woosmap.DataSearchSource.OR)
            } else {
                dataSearchSource.removeFieldFromSearchTextOptions(woosmap.$(this).val());
            }
        });

        searchview.delegate = {
            didClearSearch: function () {
                mapView.set('stores', defaultStores);
            }
        };
         //initialize the map
        dataSource.getAllStores(function (stores) {
            defaultStores = stores.features;
            mapView.set('stores', stores.features);
        });
    });

}

document.addEventListener("DOMContentLoaded", function (event) {
    WoosmapLoader.load('1.2', projectKey, woosmap_main);
});