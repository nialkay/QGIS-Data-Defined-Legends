# This is a sample Python script.

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.
import math
from qgis.core import *
from qgis.PyQt.QtCore import QVariant


def create_legend(vector_params, legend_params, legend_values):
    if vector_params['geometry_type'] == QgsWkbTypes.PointGeometry:
        legend = QgsVectorLayer("Point", legend_params['title'], "memory")
    else:
        legend = QgsVectorLayer("Linestring", legend_params['title'], "memory")
    legend.setCrs(vector_params['crs'])


    pr = legend.dataProvider()
    pr.addAttributes([QgsField(legend_params['fname'], QVariant.Double),
                      QgsField("Size", QVariant.Double),
                      QgsField("Color", QVariant.String),
                      QgsField("Legend", QVariant.String)])
    legend.updateFields()

    for value in legend_values:
        f = QgsFeature()
        if vector_params['geometry_type'] == QgsWkbTypes.PointGeometry:
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(vector_params['extent'].xMinimum(),
                                                      vector_params['extent'].yMinimum())))
        else:
            f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(vector_params['extent'].xMinimum(),
                                                  vector_params['extent'].yMinimum()),
                                                  QgsPointXY(vector_params['extent'].xMinimum() + 1,
                                                  vector_params['extent'].yMinimum() + 1)]))
        f.setAttributes([value])
        pr.addFeature(f)

    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(legend))

    with edit(legend):
        legend_count = legend_params['legend_occurrence'] - 1
        for f in legend.getFeatures():
            context.setFeature(f)

            if legend_params['override']['type'] == 'size':
                f["Size"] = legend_params['override']['value']
            elif 'size_exp' in vector_params.keys():
                f["Size"] = vector_params['size_exp'].evaluate(context)
            else:
                if vector_params['geometry_type'] == QgsWkbTypes.PointGeometry:
                    f["Size"] = vector_params['renderer_properties']['size']
                else:
                    f["Size"] = vector_params['renderer_properties']['line_width']

            if legend_params['override']['type'] == 'colour':
                f["Color"] = legend_params['override']['value']
            elif 'colour_exp' in vector_params.keys():
                f["Color"] = vector_params['colour_exp'].evaluate(context)
            else:
                f["Color"] = vector_params['renderer_properties']['color']

            if legend_count == legend_params['legend_occurrence'] - 1:
                if legend_params['decimal_places'] == 0:
                    f["Legend"] = str(int(f[legend_params['fname']]))
                else:
                    f["Legend"] = str(round(f[legend_params['fname']], legend_params['decimal_places']))
                legend_count = 0
            else:
                f["Legend"] = ''
                legend_count += 1
            legend.updateFeature(f)
    legend.updateExtents()
    QgsProject.instance().addMapLayer(legend)
    QgsProject.instance().layerTreeRoot().findLayer(legend).setItemVisibilityChecked(False)
    return legend


def graduated_renderer(legend, field, params):
    range_list = list()
    for f in legend.getFeatures():
        properties = params['renderer_properties']
        properties['offset'] = '0'
        if params['geometry_type'] == QgsWkbTypes.PointGeometry:
            properties['color'] = f["Color"]
            properties['size'] = f["Size"]
            sym = QgsMarkerSymbol.createSimple(properties)
        else:
            properties['line_color'] = f["Color"]
            properties['line_width'] = f["Size"]
            sym = QgsLineSymbol.createSimple(properties)
        rng = QgsRendererRange(f[field], f[field], sym, f["Legend"])
        range_list.append(rng)
    renderer = QgsGraduatedSymbolRenderer(field, range_list)
    legend.setRenderer(renderer)
    legend.triggerRepaint()


def read_vector_symbology(vlayer):
    # Reads vector symbology (and CRS and geometry type too).
    # Also reads the data defined expressions, and the chosen fields.
    params = dict()
    single_symbol_renderer = vlayer.renderer()
    symbol = single_symbol_renderer.symbol()
    symbol_layer = symbol.symbolLayers()[0]
    params['crs'] = vlayer.crs()
    params['geometry_type'] = vlayer.geometryType()
    if vlayer.geometryType() == QgsWkbTypes.PointGeometry:
        colour_prop = 3
        size_prop = 0
    else:
        colour_prop = 4
        size_prop = 5
    params['extent'] = vlayer.extent()
    colour_exp = symbol_layer.dataDefinedProperties().property(colour_prop).asExpression()
    if colour_exp != 'NULL' and colour_exp != '':
        params['colour_exp'] = QgsExpression(colour_exp)
        start_field = colour_exp.find('\"') + 1
        end_field = start_field + colour_exp[start_field:].find('\"')
        params['colour_field'] = colour_exp[start_field:end_field]
    size_exp = symbol_layer.dataDefinedProperties().property(size_prop).asExpression()
    if size_exp != 'NULL' and size_exp != '':
        params['size_exp'] = QgsExpression(size_exp)
        start_field = size_exp.find('\"') + 1
        end_field = start_field + size_exp[start_field:].find('\"')
        params['size_field'] = size_exp[start_field:end_field]
    params['renderer_properties'] = symbol_layer.properties()
    return params


def find_min_max(vlayer, field):
    # Function finds the minimum and maximum values in the selected field.
    vals = vlayer.fields().indexFromName(field)
    min = vlayer.minimumValue(vals)
    max = vlayer.maximumValue(vals)
    return min, max


def find_values(steps, min, max):
    # This function creates the list of values for our legend layer. Values increase linearly between minimum and maximum values.
    values = list()
    step = (max - min) / (steps - 1)
    for counter in range(steps):
        values.append(min + (counter * step))
    return values


def process_data_defined(legend_params):
    # Main function that reads vector data, creates legend layer(s), deletes any old legend, and renders the new legend layer.
    vector_parameters = read_vector_symbology(legend_params['layer'])

    legend_values = find_values(legend_params['field_1']['steps'], legend_params['field_1']['min'], legend_params['field_1']['max'])
    # Delete the old legend if it exists.
    try:
        QgsProject.instance().removeMapLayer(QgsProject.instance().mapLayersByName(legend_params['field_1']['title'])[0].id())
    except:
        pass
    legend = create_legend(vector_parameters, legend_params['field_1'], legend_values)
    graduated_renderer(legend, legend_params['field_1']['fname'], vector_parameters)

    if legend_params['single_or_double_variant'] == 'double':
        legend_values = find_values(legend_params['field_2']['steps'], legend_params['field_2']['min'], legend_params['field_2']['max'])
        # Delete the old legend if it exists.
        try:
            QgsProject.instance().removeMapLayer(QgsProject.instance().mapLayersByName(legend_params['field_2']['title'])[0].id())
        except:
            pass
        legend = create_legend(vector_parameters, legend_params['field_2'], legend_values)
        graduated_renderer(legend, legend_params['field_2']['fname'], vector_parameters)
