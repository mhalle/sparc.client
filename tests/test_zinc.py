import os
from unittest.mock import patch

import pytest

from sparc.client.zinchelper import ZincHelper

from mock_responses import mock_response_project_files_396, mock_response_project_files_426, mock_response_project_files_11

here = os.path.abspath(os.path.dirname(__file__))


def _resource(name):
    return os.path.join(here, 'resources', name)


@pytest.fixture
def zinc():
    return ZincHelper()


def test_export_scaffold_into_vtk_format(zinc):
    # create a temporary output file
    output_location = _resource('')

    # ensure the function returns None if the dataset has no Scaffold_Creator-settings.json file
    invalid_dataset_id = 1000000
    with pytest.raises(RuntimeError):
        result = zinc.get_scaffold_as_vtk(invalid_dataset_id, output_location)
        assert result is None

    # ensure the function generates a VTK file with valid content
    dataset_id = 292
    zinc.get_scaffold_as_vtk(dataset_id, output_location)

    output_file = _resource("scaffold_root.vtk")
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 0

    # Clean up the temporary output file
    os.remove(output_file)


def test_export_scaffold_into_stl_format(zinc):
    # create a temporary output file
    output_location = _resource('')

    # ensure the function returns None if the dataset has no Scaffold_Creator-settings.json file
    invalid_dataset_id = 1000000
    with pytest.raises(RuntimeError):
        result = zinc.get_scaffold_as_stl(invalid_dataset_id, output_location)
        assert result is None

    # ensure the function generates an STL file with valid content
    dataset_id = 292
    zinc.get_scaffold_as_stl(dataset_id, output_location)

    output_file = _resource("scaffold_zinc_graphics.stl")
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 0

    # Clean up the temporary output file
    os.remove(output_file)


def _mock_get_scaffold(self, dataset_id):
    self._region.readFile(_resource("cube.exf"))


def test_export_scaffold_into_stl_format_non_default_coordinates(zinc):
    # create a temporary output file
    output_location = _resource('')

    zinc._get_scaffold = _mock_get_scaffold.__get__(zinc)

    # ensure the function generates an STL file with valid content
    dataset_id = 292
    zinc.get_scaffold_as_stl(dataset_id, output_location)

    output_file = _resource("scaffold_zinc_graphics.stl")
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 0

    # Clean up the temporary output file
    os.remove(output_file)


def test_export_scaffold_into_vtk_format_with_default_output_location(zinc):
    # ensure the function generates a VTK file with valid content
    dataset_id = 292
    try:
        zinc.get_scaffold_as_vtk(dataset_id)
        assert os.path.exists("scaffold_root.vtk")
        assert os.path.getsize("scaffold_root.vtk") > 0

        # Clean up the temporary output file
        os.remove("scaffold_root.vtk")
    except (RuntimeError, TypeError):
        pass


def test_export_scaffold_into_stl_format_with_default_output_location(zinc):
    # ensure the function generates a VTK file with valid content
    dataset_id = 292
    try:
        zinc.get_scaffold_as_stl(dataset_id)

        assert os.path.exists("scaffold_zinc_graphics.stl")
        assert os.path.getsize("scaffold_zinc_graphics.stl") > 0

        # Clean up the temporary output file
        os.remove("scaffold_zinc_graphics.stl")
    except (RuntimeError, TypeError):
        pass


def test_export_mbf_to_vtk(zinc):
    # create a temporary output file
    output_file = _resource("mbf_vtk.vtk")

    # ensure the function generates a VTK file with valid content
    dataset_id = 121
    dataset_file = "11266_20181207_150054.xml"
    try:
        zinc.get_mbf_vtk(dataset_id, dataset_file, output_file)
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0

        # Clean up the temporary output file
        os.remove(output_file)
    except (RuntimeError, TypeError):
        pass


def test_export_mbf_to_vtk_with_default_output_name(zinc):
    # ensure the function generates a VTK file with valid content
    dataset_id = 121
    dataset_file = "11266_20181207_150054.xml"
    try:
        zinc.get_mbf_vtk(dataset_id, dataset_file)
        assert os.path.exists("11266_20181207_150054.vtk")
        assert os.path.getsize("11266_20181207_150054.vtk") > 0
        # Clean up the temporary output file
        os.remove("11266_20181207_150054.vtk")
    except (RuntimeError, TypeError):
        pass


def test_analyse_with_suited_input_file(zinc):
    input_file_name = _resource("3Dscaffold-CGRP-Mice-Dorsal-2.xml")
    species = "Mice"
    organ = ["stomach", "esophagus"]
    # Call the analyse function and assert that it succeeds
    suitability = zinc.analyse(input_file_name, organ, species)
    assert suitability
    assert suitability["match_percentage"] >= 90.0
    # Clean up the temporary output file
    os.remove(_resource("3Dscaffold-CGRP-Mice-Dorsal-2.exf"))


def test_analyse_with_input_file_extra_groups(zinc):
    input_file_name = _resource("3Dscaffold-CGRP-Mice-Dorsal-1.xml")
    species = "Mice"
    organ = ["stomach", "esophagus"]
    # Call the analyse function and assert that it succeeds
    suitability = zinc.analyse(input_file_name, organ, species)
    assert suitability
    assert suitability["match_percentage"] >= 60.0
    # Clean up the temporary output file
    os.remove(_resource("3Dscaffold-CGRP-Mice-Dorsal-1.exf"))


def test_analyse_with_input_file_no_data(zinc):
    input_file_name = _resource("3Dscaffold-CGRP-Mice-Dorsal-3.xml")
    species = "Mice"
    organ = ["heart"]
    expected = "Analysis failed: The groups in the file contain no geometric data (nodes)."
    # Call the analyse function and assert that it succeeds
    suitability = zinc.analyse(input_file_name, organ, species)
    assert suitability
    assert suitability["message"] == expected
    # Clean up the temporary output file
    os.remove(_resource("3Dscaffold-CGRP-Mice-Dorsal-3.exf"))


def test_analyse_with_input_file_without_coordinate_field(zinc):
    # Test file that has no coordinate field
    input_file_name = "test_input.xml"
    organ = "stomach"
    expected = (
        f"Analysis failed: The file does not contain a valid 3D coordinates field."
    )
    with open(input_file_name, "w") as f:
        f.write("<root><data>Test data</data></root>")
    # Call the analyse function and assert that it succeeds
    suitability = zinc.analyse(input_file_name, organ)
    assert suitability
    assert suitability["message"] == expected

    # Clean up the temporary output file
    os.remove(input_file_name)
    os.remove("test_input.exf")


def test_analyse_with_unhandled_organ(zinc):
    # Create a temporary input file for testing
    input_file_name = _resource("3Dscaffold-CGRP-Mice-Dorsal-1.xml")
    organ = "Brain"
    expected = f"The {organ.lower()} organ is not handled by the mapping tool."
    # Call the analyse function and assert that it raises an AssertionError
    suitability = zinc.analyse(input_file_name, organ)
    assert suitability
    assert suitability["message"] == expected


def test_analyse_with_invalid_input_file_type(zinc):
    # Create a temporary input file with an invalid extension
    input_file_name = "test_input.txt"
    organ = "stomach"
    with open(input_file_name, "w") as f:
        f.write("This is not an XML file")
    # Call the analyse function and assert that it raises a ValueError
    with pytest.raises(ValueError):
        zinc.analyse(input_file_name, organ)
    # Clean up the temporary file
    os.remove(input_file_name)


def test_analyse_with_invalid_input_file_content(zinc):
    # Create a temporary input file for testing
    input_file_name = "test_input.xml"
    organ = "stomach"
    with open(input_file_name, "w") as f:
        f.write("<root><data>Test data</root>")
    # Call the analyse function and assert that it raises an MBFXMLFormat
    with pytest.raises(Exception):
        zinc.analyse(input_file_name, organ)
    # Clean up the temporary input file
    os.remove(input_file_name)


def test_print_high_res_image(zinc):
    dataset_id = 396
    printed_image = _resource('')
    with patch('sparc.client.services.pennsieve.PennsieveService.list_files', return_value=mock_response_project_files_396):
        f = zinc.get_workflow_project_files(dataset_id)
        proj_file = f[0].copy()
        v = zinc.get_visualisation_file_from_project_file(proj_file)
        a = zinc.get_visualisation_external_sources(v)
        zinc.print_image_from_visualisation(printed_image, 'stomach', 3260, 2048, v, a)

    printed_image_file = _resource('stomach_Layout1_image.jpeg')
    assert os.path.exists(printed_image_file)
    assert os.path.getsize(printed_image_file) > 0
    # Clean up the temporary output file
    os.remove(printed_image_file)


def test_vtk_embedded_data(zinc):
    dataset_id = 396
    vtk_export_dir = _resource('')
    with patch('sparc.client.services.pennsieve.PennsieveService.list_files', return_value=mock_response_project_files_396):
        f = zinc.get_workflow_project_files(dataset_id)
        proj_file = f[0].copy()
        v = zinc.get_visualisation_file_from_project_file(proj_file)
        a = zinc.get_visualisation_external_sources(v)
        zinc.generate_vtk_from_visualisation(vtk_export_dir, 'stomach', v, a)

    for f in ['stomach_root.vtk', 'stomach_root_marker.vtk', 'stomach_vasculature_data.vtk']:
        vtk_file = _resource(f)
        assert os.path.exists(vtk_file)
        assert os.path.getsize(vtk_file) > 0
        # Clean up the temporary output file
        os.remove(vtk_file)


def test_mbfxml(zinc):
    dataset_id = 426
    vtk_export_dir = _resource('')
    with patch('sparc.client.services.pennsieve.PennsieveService.list_files', return_value=mock_response_project_files_426):
        f = zinc.get_exf_files(dataset_id)
        zinc.generate_mbfxml_from_exf(vtk_export_dir, 'nerve', f[0])

    mbfxml_file = _resource('nerve.xml')
    assert os.path.exists(mbfxml_file)
    assert os.path.getsize(mbfxml_file) > 0
    # Clean up the temporary output file
    os.remove(mbfxml_file)


def test_invalid_input_for_api(zinc):
    f = zinc.get_visualisation_file_from_project_file([])
    assert f is None
    f = zinc.get_visualisation_file_from_project_file({})
    assert f is None
    f = zinc.get_visualisation_file_from_project_file({'uri': 'https://example.com'})
    assert f is None
    info = {'name': 'map-client-workflow.proj', 'datasetId': 100000, 'datasetVersion': 999}
    f = zinc.get_visualisation_file_from_project_file(info)
    assert f is None
    f = zinc.get_visualisation_external_sources([])
    assert f is None
    info = {'name': 'a-file.txt', 'datasetId': 100000, 'datasetVersion': 999, 'uri': 'https://example.com'}
    f = zinc.get_visualisation_external_sources(info)
    assert f is None

    with patch('sparc.client.services.pennsieve.PennsieveService.list_files', return_value=mock_response_project_files_11):
        zinc.get_scaffold_as_stl(11)
        os.remove("scaffold_zinc_graphics.stl")

    with patch('sparc.client.services.pennsieve.PennsieveService.list_files', return_value=mock_response_project_files_426):
        info = {'name': 'map-client-workflow.proj', 'datasetId': 426, 'datasetVersion': 3,
                'uri': 's3://prd-sparc-discover50-use1/426/files/derivative/sub-f006/L/010-data-preparation/B824_C3L.exf'}
        zinc.get_visualisation_file_from_project_file(info)
