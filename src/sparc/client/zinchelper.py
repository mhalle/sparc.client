import json
import os
import posixpath
import re
import tempfile
from collections import namedtuple
from urllib.parse import urljoin, urlparse

from cmlibs.exporter.stl import ArgonSceneExporter as STLExporter
from cmlibs.exporter.vtk import ArgonSceneExporter as VTKExporter
from cmlibs.exporter.image import ArgonSceneExporter as ImageExporter
from cmlibs.utils.zinc.field import field_exists, get_group_list
from cmlibs.zinc.context import Context
from cmlibs.zinc.result import RESULT_OK
from mbfxml2ex.app import read_xml
from mbfxml2ex.zinc import load, write_ex
from scaffoldmaker import scaffolds
from scaffoldmaker.annotation.bladder_terms import get_bladder_term
from scaffoldmaker.annotation.body_terms import get_body_term
from scaffoldmaker.annotation.brainstem_terms import get_brainstem_term
from scaffoldmaker.annotation.colon_terms import get_colon_term
from scaffoldmaker.annotation.esophagus_terms import get_esophagus_term
from scaffoldmaker.annotation.heart_terms import get_heart_term
from scaffoldmaker.annotation.lung_terms import get_lung_term
from scaffoldmaker.annotation.muscle_terms import get_muscle_term
from scaffoldmaker.annotation.nerve_terms import get_nerve_term
from scaffoldmaker.annotation.smallintestine_terms import \
    get_smallintestine_term
from scaffoldmaker.annotation.stellate_terms import get_stellate_term
from scaffoldmaker.annotation.stomach_terms import get_stomach_term
from scaffoldmaker.utils.exportvtk import ExportVtk

from sparc.client.services.pennsieve import PennsieveService


def create_pennsieve_service():
    pennsieve_config = {"pennsieve_profile_name": "zinc_helper"}
    p = PennsieveService(config=pennsieve_config, connect=False)
    return p


class ZincHelper:
    """
    A helper class for working with Zinc and scaffoldmaker.

    Attributes:
        _allOrgan (dict): A dictionary mapping organ names to their corresponding scaffoldmaker term functions.
        _context (Context): A Zinc context object.
        _region (Region): A Zinc region object.
        _pennsieveService (PennsieveService): A Pennsieve service object for file operations.

    Methods:
        download_files: Downloads files from Pennsieve.
        get_scaffold_vtk: Generates a VTK file for the scaffold settings of a dataset.
        get_mbf_vtk: Generates a VTK file for an MBF XML segmentation file.
        analyse: Analyses an MBF XML file for mapping suitability to a specified organ.
    """

    def __init__(self):
        """
        Initializes the ZincHelper class.
        """
        self._allOrgan = {
            "bladder": get_bladder_term,
            "body": get_body_term,
            "brainstem": get_brainstem_term,
            "colon": get_colon_term,
            "esophagus": get_esophagus_term,
            "heart": get_heart_term,
            "lung": get_lung_term,
            "muscle": get_muscle_term,
            "nerve": get_nerve_term,
            "smallintestine": get_smallintestine_term,
            "stellate": get_stellate_term,
            "stomach": get_stomach_term,
        }
        self._context = Context("sparcclient")
        self._region = self._context.getDefaultRegion()
        self._pennsieveService = PennsieveService(connect=False)

    def download_files(
        self,
        limit=10,
        offset=0,
        file_type=None,
        query=None,
        organization=None,
        organization_id=None,
        dataset_id=None,
    ):
        """
        Downloads files from Pennsieve.

        Args:
            limit (int): The maximum number of files to download.
            offset (int): The offset for the file listing.
            file_type (str): The type of files to download (e.g., 'JSON', 'XML').
            query (str): The query string to filter the files.
            organization (str): The organization name to filter the files.
            organization_id (int): The organization ID to filter the files.
            dataset_id (int): The dataset ID to filter the files.

        Returns:
            str: The name of the downloaded file.

        Raises:
            RuntimeError: If the dataset fails to download.
        """
        file_list = self._pennsieveService.list_files(
            limit, offset, file_type, query, organization, organization_id, dataset_id
        )
        if not file_list:
            raise RuntimeError("The dataset failed to download.")

        try:
            response = self._pennsieveService.download_file(file_list)
        except AssertionError:
            raise RuntimeError("The dataset failed to download.")

        assert response.status_code == 200
        return file_list[0]["name"]

    def _get_scaffold(self, dataset_id):
        """
        Get a scaffold settings file from the Pennsieve.

        Args:
            dataset_id (int): The ID of the dataset to generate the VTK file for.
        """
        scaffold_setting_file = self.download_files(
            limit=1,
            file_type="JSON",
            query=".*settings.json",
            dataset_id=dataset_id,
        )
        with open(scaffold_setting_file) as f:
            c = json.load(f)

        os.remove(scaffold_setting_file)

        assert "scaffold_settings" in c
        assert "scaffoldPackage" in c["scaffold_settings"]

        sm = scaffolds.Scaffolds_decodeJSON(c["scaffold_settings"]["scaffoldPackage"])
        sm.generate(self._region)

    def get_scaffold_as_vtk(self, dataset_id, output_location=None):
        """
        Generates a VTK file from the scaffold settings defined in a dataset.

        Args:
            dataset_id (int): The ID of the dataset to generate the VTK file for.
            output_location (str): The output location for the generated VTK file.
            If not provided, a default of the current working directory is used.
        """
        self._get_scaffold(dataset_id)

        ex = VTKExporter("." if output_location is None else output_location, "scaffold")
        ex.export_from_scene(self._region.getScene())

    def get_scaffold_as_stl(self, dataset_id, output_location=None):
        """
        Generates an STL file from the scaffold settings defined in a dataset.

        Args:
            dataset_id (int): The ID of the dataset to generate the STL file for.
            output_location (str): The output location for the generated STL file.
            If not provided, a default of the current working directory is used.
        """
        self._get_scaffold(dataset_id)

        ex = STLExporter("." if output_location is None else output_location, "scaffold")
        scene = self._region.getScene()
        surfaces = scene.createGraphicsSurfaces()
        surfaces.setBoundaryMode(surfaces.BOUNDARY_MODE_BOUNDARY)

        fm = self._region.getFieldmodule()
        coordinates = fm.findFieldByName("coordinates")
        if not coordinates.isValid():
            field_iterator = fm.createFielditerator()
            field = field_iterator.next()
            while field.isValid() and not coordinates.isValid():
                if field_exists(fm, field.getName(), "FiniteElement", 3):
                    coordinates = field

                field = field_iterator.next()

        surfaces.setCoordinateField(coordinates)
        ex.export_stl_from_scene(scene)

    def get_mbf_vtk(self, dataset_id, dataset_file, output_file=None):
        """
        Generates a VTK file for an MBF XML segmentation file.

        Args:
            dataset_id (int): The ID of the dataset to generate the VTK file for.
            dataset_file (str): The name of the MBF XML segmentation file.
            output_file (str): The name of the output VTK file.
                If not provided, dataset_file name with a vtk extension will be used.
        """
        segmentation_file = self.download_files(
            limit=1,
            file_type="XML",
            query=dataset_file,
            dataset_id=dataset_id,
        )
        contents = read_xml(segmentation_file)
        load(self._region, contents, None)
        ex = ExportVtk(self._region, "MBF XML VTK export.")
        if output_file is None:
            output_file = os.path.splitext(dataset_file)[0] + ".vtk"
        ex.writeFile(output_file)
        os.remove(segmentation_file)

    def analyse(self, input_data_file_name, organs, species=None):
        """
        Analyses an MBF XML file for mapping suitability to a specified organ.

        Args:
            input_data_file_name (str): The name of the input MBF XML file.
            organs (str or list): The name of the organ(s) to analyse.
                It can be a single string representing one organ or a list of strings representing multiple organs.
            species (str, optional): The name of the species. Defaults to None.

        Returns:
            str: The analysis result message.

        Raises:
            ValueError: If the input file is not an MBF XML file.
        """

        # Check input organ and convert to a list if it's a single string
        get_terms = []
        if isinstance(organs, str):
            organs = [organs]

        # Loop through each organ in the list
        for organ in organs:
            # Convert the organ name to lowercase for case-insensitive comparison
            organ = organ.lower()

            # Check if the provided organ is handled by the mapping tool
            if organ not in self._allOrgan:
                return f"The {organ} organ is not handled by the mapping tool."

            # Get the corresponding term (function) for the organ from the mapping tool
            get_term = self._allOrgan[organ]
            get_terms.append(get_term)

        # Check if the input file is an XML file
        if not input_data_file_name.endswith(".xml"):
            raise ValueError("Input file must be an MBF XML file")

        # Read the input data file and write the contents to an ex file
        ex_file_name = os.path.splitext(input_data_file_name)[0] + ".exf"
        write_ex(ex_file_name, read_xml(input_data_file_name))

        # Read the ex file and ensure that it was loaded successfully
        result = self._region.readFile(ex_file_name)
        assert result == RESULT_OK, f"Failed to load data file {input_data_file_name}"

        # Get groups that were loaded from the ex file
        fieldmodule = self._region.getFieldmodule()
        groupNames = [group.getName() for group in get_group_list(fieldmodule)]

        # If the ex file doesn't have any groups, it's not suitable for mapping
        if not groupNames:
            return (
                f"The data file {input_data_file_name} doesn't have any groups, "
                f"therefore this data file is not suitable for mapping."
            )

        # Get groups that are not suitable for mapping.
        not_in_scaffoldmaker = self.get_groups_not_in_scaffoldmaker(groupNames, get_terms)

        # Generate the analysis result message based on the suitability of the groups
        suited_text = f"The data file {input_data_file_name} is suited for mapping to the given organ."
        not_in_text = f"However, the mapping tool does not have the following groups defined by default; {', '.join(not_in_scaffoldmaker)}."

        return f"{suited_text} {not_in_text}" if not_in_scaffoldmaker else suited_text

    @staticmethod
    def get_groups_not_in_scaffoldmaker(group_names, get_terms):
        """
        Identify and return groups that are not suitable for mapping in ScaffoldMaker.

        Parameters:
            group_names (list): A list of strings containing group names to be evaluated.
            get_terms (list): A list of functions, each capable of determining the suitability of a group
                             for mapping based on specific criteria.

        Returns:
            list: A list of group names that are not suitable for mapping in ScaffoldMaker.
        """
        # Regular expression pattern to extract group ID from Trace Association URL
        regex = r"\/*([a-zA-Z]+)_*(\d+)"
        not_in_scaffoldmaker = []

        # Iterate through the group names and check their suitability for mapping
        for group in group_names:
            # Skip the 'marker' group
            if group == "marker":
                continue

            # Check if the group name matches the regex pattern and format it accordingly
            matches = re.search(regex, group)
            if matches and len(matches.groups()) == 2:
                group = f"{matches.groups()[0].upper()}:{matches.groups()[1]}"

            # Check if the group can be handled by the mapping tool for any of the specified organs
            for get_term in get_terms:
                try:
                    get_term(group)
                    if group in not_in_scaffoldmaker:
                        not_in_scaffoldmaker.remove(group)
                    break
                except NameError:
                    if group not in not_in_scaffoldmaker:
                        not_in_scaffoldmaker.append(group)

        return not_in_scaffoldmaker

    @staticmethod
    def get_workflow_project_files(dataset_id):
        p = create_pennsieve_service()
        r = p.list_files(limit=200, dataset_id=dataset_id, file_type="GenericData", query="map-client-workflow.proj")
        return [f for f in r if f['name'] == 'map-client-workflow.proj']

    @staticmethod
    def get_visualisation_file_from_project_file(project_file_info):
        if not isinstance(project_file_info, dict):
            return None

        if project_file_info.get('name') != 'map-client-workflow.proj':
            return None

        p = create_pennsieve_service()

        with tempfile.TemporaryDirectory() as temp_dir:
            proj_file_path = os.path.join(temp_dir, "map-client-workflow.proj")
            response = p.download_file(project_file_info, proj_file_path)

            if _deal_with_download_file_response(response) != 200:
                return None

            with open(proj_file_path) as fh:
                content = fh.read()

            node_info = _extract_node_info(content)
            if not node_info:
                return None

            conf_file_name = f"{node_info['identifier']}.conf"
            conf_file_path = os.path.join(temp_dir, conf_file_name)

            project_file_info.update({
                'name': conf_file_name,
                'uri': project_file_info['uri'].replace('map-client-workflow.proj', conf_file_name)
            })

            response = p.download_file(project_file_info, conf_file_path)
            if _deal_with_download_file_response(response) != 200:
                return None

            with open(conf_file_path) as fh:
                conf_content = json.load(fh)

            visualisation_doc = conf_content.get("visualisation-doc")
            if not visualisation_doc:
                return None

            updated_file_info = {
                'name': visualisation_doc,
                'uri': project_file_info['uri'].replace(
                    conf_file_name,
                    os.path.join(f"{node_info['identifier']}-previous-docs", visualisation_doc)
                )
            }

            project_file_info.update(updated_file_info)

        return project_file_info

    @staticmethod
    def get_visualisation_external_sources(visualisation_file_info):
        if not _is_valid_resource_info(visualisation_file_info):
            return None

        p = create_pennsieve_service()

        with tempfile.TemporaryDirectory() as temp_dir:
            visualisation_file_path = os.path.join(temp_dir, "visualisation-doc.json")
            response = p.download_file(visualisation_file_info, visualisation_file_path)

            if _deal_with_download_file_response(response) != 200:
                return None

            with open(visualisation_file_path) as fh:
                content = fh.read()

            json_content = json.loads(content)
            model_sources = _extract_model_sources(json_content)
            data_file_uris = _construct_absolute_uris(visualisation_file_info, model_sources)

        return data_file_uris

    @staticmethod
    def print_image_from_visualisation(printed_image_location, printed_image_prefix, width, height, visualisation_file_info, model_file_info):
        p = create_pennsieve_service()

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed_uri = urlparse(visualisation_file_info['uri'])
            visualisation_file_location = os.path.join(temp_dir, parsed_uri.path.lstrip('/'))
            os.makedirs(os.path.dirname(visualisation_file_location), exist_ok=True)
            response = p.download_file(visualisation_file_info, visualisation_file_location)
            for model_info in model_file_info:
                model_parsed_uri = urlparse(model_info['uri'])
                target_location = os.path.join(temp_dir, model_parsed_uri.path.lstrip('/'))
                os.makedirs(os.path.dirname(target_location), exist_ok=True)
                response = p.download_file(model_info, target_location)

            exporter = ImageExporter(width, height, output_target=printed_image_location, output_prefix=printed_image_prefix)
            exporter.set_filename(visualisation_file_location)
            exporter.export()


def _construct_absolute_uris(base_info, relative_file_info):
    # Extract the base path from the URI (everything up to the last '/')
    parsed_uri = urlparse(base_info['uri'])
    base_dir = posixpath.dirname(parsed_uri.path)

    # Construct absolute URIs
    absolute_uris = []
    for file_info in relative_file_info:
        relative_path = file_info['FileName']
        resolved_path = posixpath.normpath(posixpath.join(base_dir, relative_path))
        absolute_uri = f"{parsed_uri.scheme}://{parsed_uri.netloc}{resolved_path}"
        absolute_uris.append({
            'name': posixpath.basename(relative_path),
            'datasetId': base_info['datasetId'],
            'datasetVersion': base_info['datasetVersion'],
            'uri': absolute_uri
        })

    return absolute_uris


def _is_valid_resource_info(info):
    if not isinstance(info, dict):
        return False

    return _has_required_fields(info)


def _extract_model_sources(data):
    sources = []

    def _recursive_search(obj):
        if isinstance(obj, dict):
            # Check if this dict contains a "Model" block with "Sources"
            if "Model" in obj and "Sources" in obj["Model"]:
                sources.append(*obj["Model"]["Sources"])
            # Continue searching recursively in all values
            for key, value in obj.items():
                if key == "Materials":
                    continue
                _recursive_search(value)
        elif isinstance(obj, list):
            for item in obj:
                _recursive_search(item)

    _recursive_search(data)
    return sources


def _has_required_fields(data):
    required_keys = ['name', 'uri', 'datasetId', 'datasetVersion']
    return all(key in data and data[key] not in [None, '', []] for key in required_keys)


def _deal_with_download_file_response(response):
    try:
        json_response = response.json()
        if 'status' in json_response:
            return json_response['status']
    except json.JSONDecodeError:
        return response.status_code

    return 200


def _extract_node_info(file_content, target_name="Argon Viewer"):
    node_number = None

    # Step 1: Find the node number for the target name
    for line in file_content.splitlines():
        match = re.match(r"nodelist\\(\d+)\\name=(.+)", line)
        if match and match.group(2) == target_name:
            node_number = match.group(1)
            break

    if node_number is None:
        return None  # Target name not found

    # Step 2: Extract connections and identifier for that node
    connections = None
    identifier = None

    for line in file_content.splitlines():
        if line.startswith(f"nodelist\\{node_number}\\connections\\size="):
            connections = int(line.split("=", 1)[1])
        elif line.startswith(f"nodelist\\{node_number}\\identifier="):
            identifier = line.split("=", 1)[1]

    return {
        "node_number": node_number,
        "identifier": identifier,
        "connections": connections
    }
