from dataclasses import dataclass
import numpy as np
import logging
import os
from tkinter import ttk
from tkinter import *
from tkinter import filedialog
from tktooltip import ToolTip
from typing import Union, List, Tuple

import modelsmart as ms

LOGGING_LEVEL = logging.DEBUG
LOG_FILE = "convert.log"

def setup_logging() -> None:
    # Check if the log file can be created or written to
    try:
        # Attempt to open the file in append mode
        with open(LOG_FILE, 'a') as f:
            pass  # If this succeeds, the file is writable
    except (IOError, OSError) as e:
        print(f"Error: Cannot write to log file '{LOG_FILE}'. Falling back to console logging.")
        logging.basicConfig(
            level=LOGGING_LEVEL,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # If writable, proceed with file logging
        logging.basicConfig(
            level=LOGGING_LEVEL,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            filename=LOG_FILE,
        )

setup_logging()
logging.info("Logging setup complete.")



def clean_dimension_input(dimension):
    return ''.join(char for char in dimension if char.isdigit() or char == '.' or char == '-')

@dataclass
class Node:
    label: str
    x: float
    y: float
    z: float

    def get_coordinates(self) -> list[float]:
        return [self.x, self.y, self.z]
    
def get_extreme_coords(items: List[Union[Node,ms.Joint]]) -> tuple[float, float, float, float, float, float]:
    """
    Finds the extreme x, y, and z coordinates from a list of Node or Joint instances.
    Will work with any object that has x, y, and z attributes.

    Parameters
    ----------
    items : List[Union[Node, modelsmart.Joint]]
        A list of Node or Joint instances.

    Returns
    -------
    tuple[float, float, float, float, float, float]
        The minimum and maximum x, y, z coordinates.
    """
    min_x = min([item.x for item in items]) 
    min_y = min([item.y for item in items])
    min_z = min([item.z for item in items])

    max_x = max([item.x for item in items])
    max_y = max([item.y for item in items])
    max_z = max([item.z for item in items])


    return min_x, min_y, min_z, max_x, max_y, max_z

@dataclass
class Shape:
    name: str
    height: float
    thickness: float
    width: float
    radius: float = 0

@dataclass
class Member:
    label: str
    design_list: str
    shape_label: str
    views: str
    # These are the node numbers in sequential order and not the node label for some reason in the RISA format
    inode: int
    jnode: int
    knode: int
    rotation: float
    offset: int
    material: int
    height: float = 0
    width: float = 0
    thickness: float = 0
    radius: float = 0
    theta_yz: float = 0
    theta_xz: float = 0
    theta_xy: float = 0

    def __post_init__(self) -> None:
        dimensions = self.shape_label.upper().split('X')
        if len(dimensions) == 2:
            self.radius = float(clean_dimension_input(dimensions[0]))
        elif len(dimensions) == 3:
            self.height = float(clean_dimension_input(dimensions[0]))
            self.width = float(clean_dimension_input(dimensions[1]))
            self.thickness = float(clean_dimension_input(dimensions[2]))
        else:
            logging.warning(f"Dimesions not found for member: {self.label}, shape: {self.shape_label}")
    
    def get_i_coordinates(self,nodes) -> list[float]:
        x,y,z = nodes[self.inode-1].get_coordinates()
        return [x,y,z]
    
    def get_j_coordinates(self,nodes) -> list[float]:
        x,y,z = nodes[self.jnode-1].get_coordinates()
        return [x,y,z]
    
    def set_views(self,nodes: list[Node], extreme_coords: tuple) -> None:
        ix, iy, iz = nodes[self.inode-1].get_coordinates()
        jx, jy, jz = nodes[self.jnode-1].get_coordinates()

        if iy == extreme_coords[4] and jy == extreme_coords[4]:
            self.views.append('top')
        if iy == extreme_coords[1] and jy == extreme_coords[1]:
            self.views.append('bottom')
        if iz == extreme_coords[2] and jz == extreme_coords[2]:
            self.views.append('side1')
        if iz == extreme_coords[5] and jz == extreme_coords[5]:
            self.views.append('side2')


# Constants
BACKGROUND_COLOR = 'lightblue'
HEADINGS = ['UNITS', 'NODES','.MEMBERS_MAIN_DATA','SHAPES_LIST']
END = 'END'

def get_units(data) -> dict[str, str]:
    # Unit Format: length_units  dim_units
    units_text = {}
    data = data[0].split(' ')
    #Check length_units and translate into text-based flags.
    match data[1]:
        case '0':
            units_text['length_units'] = 'ft'
        case '1':
            units_text['length_units'] = 'in'
        case '2':
            units_text['length_units'] = 'm'
        case '3':
            units_text['length_units'] = 'cm'
        case '4':
            units_text['length_units'] = 'mm'
    
    #Check dim_units and translate into text-based flags.
    match data[2]:
        case'0':
            units_text['dim_units'] = 'in'
        case '1':
            units_text['dim_units'] = 'cm'
        case '2':
            units_text['dim_units'] = 'mm'
    
    return units_text

# This function is used to get the nodes from the risa file
def get_nodes(data) -> list[Node]:
    # Node Format: Name/ID  X coord, Y coord, Z coord
    nodes = []
    for line in data:
        line = line[1:-2].strip().split('"')
        line[0] = line[0].strip()
        label = line[0]
        line = line[1].split()
        x = float(line[0])
        y = float(line[1])
        z = float(line[2])
        node = Node(label, x, y, z)
        nodes.append(node)
    return nodes

# This function is used to get the memebers from the risa file
def get_members(data: list[str]) -> list[Member]:
    members = []
    for line in data:
        line = line[1:-2].strip().split('"')
        for i,s in enumerate(line):
            line[i] = s.strip('"')
            line[i] = s.strip()
        line.pop(1)
        line.pop(2)
        temp = line[3].split()

        label = line[0]
        design_list = line[1]
        shape_label = line[2]
        inode = int(temp[0])
        jnode = int(temp[1])
        knode = int(temp[2])
        rotation = float(temp[3])
        offset = int(temp[4])
        material = int(temp[7])
        views = ['3D']

        member = Member(label, design_list, shape_label, views, inode, jnode, knode, rotation, offset, material)
        members.append(member)
    return members

def get_shapes_list(data: list[str]) -> dict[str, Shape]:
    shapes = {}
    for line in data:
        line = line[1:-2].strip().split('"')
        shape_name = line[0].strip()
        shape_properties = line[1].strip().split()

        if float(shape_properties[6]) != float(0):
            shape = Shape(shape_name, 
                        float(shape_properties[4]), 
                        float(shape_properties[5]), 
                        float(shape_properties[6]))
        else:
            shape = Shape(shape_name, 
                        float(0), 
                        float(shape_properties[5]), 
                        float(shape_properties[6]),
                        float(shape_properties[4]))    
        shapes[shape_name] = shape

    return shapes

def set_member_dimensions(members: list[Member], shapes: dict[str, Shape]) -> None:
    for member in members:
        if member.shape_label in shapes:
            shape: Shape = shapes[member.shape_label]
            member.height = shape.height
            member.width = shape.width
            member.thickness = shape.thickness
            member.radius = shape.radius
        else:
            logging.error(f"Shape not found: {member.shape_label}")

def get_orthogonal_vectors(vector: np.array) -> tuple[np.array, np.array]:
    """
    This function takes a vector and returns two orthogonal vectors to it.

    Parameters
    ----------
    vector : np.array
        The input vector to find orthogonal vectors for.
    
    Returns
    -------
    tuple[np.array, np.array]
        A tuple containing the two orthogonal vectors to the input vector.
    """
    if vector.ndim != 1 or vector.shape[0] != 3:
        logging.error("Vector must be a 3D column vector.")
        return np.array([0, 0, 0]), np.array([0, 0, 0])


    norm = np.linalg.norm(vector)
    if norm == 0:
        logging.error("Zero division error input has no magnitude")

    unit_norm = vector / norm
    
    if np.allclose(unit_norm, [1, 0, 0]) or np.allclose(unit_norm, [-1, 0, 0]):
        temp_vector = np.array([0, 1, 0])  # Use y-axis if aligned with x-axis
    elif np.allclose(unit_norm, [0, 1, 0]) or np.allclose(unit_norm, [0, -1, 0]):
        temp_vector = np.array([0, 0, 1])  # Use z-axis if aligned with y-axis
    else:
        temp_vector = np.array([1, 0, 0])  # Default to x-axis otherwise

    v1 = np.cross(unit_norm, temp_vector)
    v1 = v1 / np.linalg.norm(v1)
    v2 = np.cross(unit_norm, v1)
    v2 = v2 / np.linalg.norm(v2)

    return v1, v2

def rotate_vector(axis: np.array, angle: float) -> np.array:
    """
    This function uses Rodrigues' Rotation Formula to rotate a vector about an axis by a given angle.
    """
    angle = np.radians(angle)
    cos_theta = np.cos(angle)
    sin_theta = np.sin(angle)
    one_minus_cos = 1 - cos_theta

    x, y, z = axis  # Components of the normalized rotation axis
    rot = np.array([
        [cos_theta + x * x * one_minus_cos, x * y * one_minus_cos - z * sin_theta, x * z * one_minus_cos + y * sin_theta],
        [y * x * one_minus_cos + z * sin_theta, cos_theta + y * y * one_minus_cos, y * z * one_minus_cos - x * sin_theta],
        [z * x * one_minus_cos - y * sin_theta, z * y * one_minus_cos + x * sin_theta, cos_theta + z * z * one_minus_cos]
    ])

    return rot

def generate_face_vectors(i_coords: list[float], j_coords: list[float], rotation: float = 0) -> Tuple[np.array, np.array, np.array]:
    """
    Prepare the direction vector and orthogonal vectors for a member.

    Parameters
    ----------
    i_coords : list[float]
        Coordinates of the i-node.
    j_coords : list[float]
        Coordinates of the j-node.
    rotation : float, optional
        Rotation angle in degrees, by default 0.

    Returns
    -------
    Tuple[np.array, np.array, np.array]
        The direction vector, and two orthogonal vectors (v1, v2).
        Returns empty arrays if the direction vector has zero length.
    """
    i_vec = np.array(i_coords)
    j_vec = np.array(j_coords)
    dir_vec = j_vec - i_vec

    # Normalize the direction vector
    if np.linalg.norm(dir_vec) == 0:
        logging.error("Direction vector has zero length.")
        return np.array([]), np.array([]), np.array([])
    dir_vec = dir_vec / np.linalg.norm(dir_vec)

    # Get orthogonal vectors
    v1, v2 = get_orthogonal_vectors(dir_vec)

    # Apply rotation if specified
    if rotation != 0:
        rot_matrix = rotate_vector(dir_vec, rotation)  # Rotate around the member's axis
        v1 = np.dot(rot_matrix, v1)
        v2 = np.dot(rot_matrix, v2)

    return dir_vec, v1, v2

def gen_rect_face_vertices(i_coords: list[float], j_coords: list[float], rotation, width, height) -> np.array:

    dir_vec, v1, v2 = generate_face_vectors(i_coords, j_coords, rotation)
    i_vec = np.array(i_coords)
    j_vec = np.array(j_coords)

    if rotation != 0:
        rot_matrix = rotate_vector(dir_vec, rotation)  # Rotate around the member's axis
        v1 = np.dot(rot_matrix, v1)
        v2 = np.dot(rot_matrix, v2)

    half_width_vec = width / 2 * v1
    half_height_vec = height / 2 * v2

    # Create the four corners of the face
    corners = [
        i_vec + half_width_vec + half_height_vec,
        i_vec - half_width_vec + half_height_vec,
        i_vec - half_width_vec - half_height_vec,
        i_vec + half_width_vec - half_height_vec,

        j_vec + half_width_vec + half_height_vec,
        j_vec - half_width_vec + half_height_vec,
        j_vec - half_width_vec - half_height_vec,
        j_vec + half_width_vec - half_height_vec
    ]

    return corners

def gen_circ_face_vertices(i_coords: list[float], j_coords: list[float], radius:float, options):
    dir_vec, v1, v2 = generate_face_vectors(i_coords, j_coords)
    i_vec = np.array(i_coords)
    j_vec = np.array(j_coords)

    half_width_vect = v1 * radius/2
    half_height_vect = v2 * radius/2
   
    circle_size = int(options["Cyl"])
    arc_deg = 2*np.pi/circle_size

    corners = []
    # Create the i-node vertices
    corners.append(i_vec)
    corners.append(i_vec + half_width_vect)
    for i in range(1, circle_size):
        corners.append(i_vec + np.cos(i*arc_deg)*half_width_vect + np.sin(i*arc_deg)*half_height_vect)
    # Create the j-node vertices
    corners.append(j_vec)
    corners.append(j_vec + half_width_vect)
    for i in range(1, circle_size):
        corners.append(j_vec + np.cos(i*arc_deg)*half_width_vect + np.sin(i*arc_deg)*half_height_vect)

    faces = []
    # Create the i-node meshes
    for i in range(2, circle_size+1):
        faces.append([1, i, i+1])
        if i == circle_size:
            faces.append([1, i+1, 2])
    # Create the j-node meshes
    for i in range(2+circle_size, 2*circle_size+2):
        faces.append([circle_size+2, i, i+1])
        if i == 2*circle_size+1:
            faces.append([circle_size+2, i+1, 19])
    # Create the i->j meshes
    for i in range(2, circle_size+2):
        if i == circle_size+1:
            faces.append([i, 2, i+1+circle_size])
        else:
            faces.append([i, i+1, i+1+circle_size])
    # Create the j->i meshes
    for i in range(3+circle_size, 2*circle_size+3):
        if i == 2*circle_size + 2:
            faces.append([2, i, circle_size+3])
        else:
            faces.append([i-circle_size, i, i+1])

    return corners, faces

def create_folder(dest_dir, filename, subs_flag):
    new_folder = dest_dir + '\\' + filename

    logging.info(f"Verifying {dest_dir} exists...")
    if os.path.exists(dest_dir):
        logging.info(f"{dest_dir} is exists. Checking writability...")
        if os.access(dest_dir, os.W_OK):
            logging.info(f"{dest_dir} is writable.")
            if subs_flag and not os.path.exists(new_folder):
                logging.info(f"Creating subfolder {new_folder}...")
                if not os.path.exists(new_folder):
                    os.mkdir(new_folder)
                    if os.path.exists(new_folder):
                        logging.info(f"{new_folder} successfully created.")
                        return new_folder
                    else:
                        logging.error(f"Subfolder creation failed.")
                        logging.error(f"Reverting to {dest_dir}.")
                        return os.getcwd()
            elif subs_flag:
                return new_folder
            else:
                return dest_dir
        else:
            logging.error(f"{dest_dir} is not writable. Reverting back to current working directory.")
            return os.getcwd()
    else:
        logging.error(f"{dest_dir} does not exist. Reverting back to current working directory.")
        return os.getcwd()

def export_views_to_obj(generated_views, srcfilename, options):
    folder = create_folder(options["Dest"], srcfilename, options["Subs"])
    for view in generated_views:
        if len(view) > 2:
            vertices = view[0]
            faces = view[1]
            filename = view[2]
            print(filename)
            logging.info(f"Writing {filename}.obj")
            obj_file = open(folder + "\\" + filename + ".obj", "w")
            for vertex in vertices:
                obj_file.write(f"v {vertex[0]} {vertex[1]} {vertex[2]}\n")
            for face in faces:
                obj_file.write(f"f {' '.join(map(str, face))}\n")
            
            if os.path.exists(folder + "\\" + filename + ".obj"):
                logging.info(f"File {filename} successfully created.")
            else:
                logging.error(f"Error creating {filename}.")
        else:
            logging.error(f"{view[0]}{view[1]}.")

def gen_view(members, nodes, filename, view, options):

    # this technially "works" with modelsmart files but
    # needs to be fixed so that it is really modular
    logging.info(f"Generating {view} view")
    all_vertices =[]
    all_faces = []
    vertex_count = 0


    for member in members:
        if view in member.views:
            if(member.radius == 0):
                faces = [
                        [1, 2, 3, 4],  # Bottom face
                        [5, 6, 7, 8],  # Top face
                        [1, 2, 6, 5],  # Side face
                        [2, 3, 7, 6],  # Side face
                        [3, 4, 8, 7],  # Side face
                        [4, 1, 5, 8]   # Side face
                    ]
                ix, iy, iz = member.get_i_coordinates(nodes)
                jx, jy, jz = member.get_j_coordinates(nodes)

                corners = gen_rect_face_vertices([ix,iy,iz], [jx,jy,jz], member.rotation, member.width, member.height)
            else:
                ix, iy, iz = member.get_i_coordinates(nodes)
                jx, jy, jz = member.get_j_coordinates(nodes)
                corners, faces = gen_circ_face_vertices([ix,iy,iz],[jx,jy,jz],member.radius,options)

            faces = [[vertex_count +idx for idx in face] for face in faces]
            all_vertices.extend(corners)
            all_faces.extend(faces)
            vertex_count += corners.__len__()
    if len(all_vertices) == 0:
        logging.error("No members found for gen_view")
        return_arr = ["No members found for ", filename + '_' + view]
        return return_arr
    return np.round(all_vertices, decimals=int(options["Prec"])), all_faces, filename + '_' + view

def convert(file_list, dest_dir, dim_var, side, top, bottom, cyl_vert, coord_prec):
    file_list = file_list.get().split('\'')
    files = []
    for i in file_list:
        if ',' not in i and i != '(' and i != ')':
            files.append(i)

    for filepath in files:
        logging.info("Conveting file: " + filepath)

        options = {"Dest": dest_dir.get(), "Dim": dim_var.get(), "Cyl": cyl_vert.get(), "Prec": coord_prec.get(), "Subs": True}

        if not os.path.exists(filepath):
            logging.error("File not found")
            return

        filename = filepath.split('/')[-1]
        if ".r3d" in filename:
            filename = filename.strip('.r3d')
            nodes = []
            members = []
            try:
                with open(filepath, 'r') as file:
                    for line in file:
                        for heading in HEADINGS:
                            if heading in line and "END" not in line:
                                line = line.strip()
                                num_entries = int(line.split('<')[-1].strip('>'))
                                data = []
                                match heading:
                                    case 'UNITS':
                                        for i in range(num_entries):
                                            data.append(file.readline().strip())
                                        units = get_units(data)
                                    case 'NODES':
                                        for i in range(num_entries):
                                            data.append(file.readline().strip())
                                        nodes = get_nodes(data)
                                    case '.MEMBERS_MAIN_DATA':
                                        for i in range(num_entries):
                                            data.append(file.readline())
                                        members = get_members(data)
                                    case 'SHAPES_LIST':
                                        for i in range(num_entries):
                                            data.append(file.readline())
                                        shapes = get_shapes_list(data)
            except FileNotFoundError:
                logging.error("File not found")
                return
            except PermissionError:
                logging.error("Permission denied, could not read file")
                return
            except Exception as e:
                logging.error("An unknown error occurred")
                return

            set_member_dimensions(members, shapes)
            for member in members:
                member.set_views(nodes, get_extreme_coords(nodes))

            generated_views = []
            if dim_var.get() == '3D':
                generated_views.append(gen_view(members, nodes, filename, '3D', options))
            elif dim_var.get() == 'All':
                generated_views.append(gen_view(members, nodes, filename, '3D', options))
                if side.get():
                    generated_views.append(gen_view(members, nodes, filename, 'side1', options))
                    generated_views.append(gen_view(members, nodes, filename, 'side2', options))
                if top.get():
                    generated_views.append(gen_view(members, nodes, filename, 'top', options))
                if bottom.get():
                    generated_views.append(gen_view(members, nodes, filename, 'bottom', options))
            elif dim_var.get() == '2D':
                if side.get():
                    generated_views.append(gen_view(members, nodes, filename, 'side1', options))
                    generated_views.append(gen_view(members, nodes, filename, 'side2', options))
                if top.get():
                    generated_views.append(gen_view(members, nodes, filename, 'top' , options))
                if bottom.get():
                    generated_views.append(gen_view(members, nodes, filename, 'bottom', options))

            export_views_to_obj(generated_views, filename, options)
            logging.info("File successfully converted")
            logging.info("Starting write process...")
    
        elif ".3dd" in filename:
            filename = filename.strip('.3dd')
            joints, members, shapes = ms.parse_file(filepath)
            for member in members:
                member.set_views(joints, get_extreme_coords(joints))

            generated_views = []
            if dim_var.get() == '3D':
                generated_views.append(gen_view(members, joints, filename, '3D', options))
            elif dim_var.get() == 'All':
                generated_views.append(gen_view(members, joints, filename, '3D', options))
                if side.get():
                    generated_views.append(gen_view(members, joints, filename, 'side1', options))
                    generated_views.append(gen_view(members, joints, filename, 'side2', options))
                if top.get():
                    generated_views.append(gen_view(members, joints, filename, 'top', options))
                if bottom.get():
                    generated_views.append(gen_view(members, joints, filename, 'bottom', options))
            elif dim_var.get() == '2D':
                if side.get():
                    generated_views.append(gen_view(members, joints, filename, 'side1', options))
                    generated_views.append(gen_view(members, joints, filename, 'side2', options))
                if top.get():
                    generated_views.append(gen_view(members, joints, filename, 'top' , options))
                if bottom.get():
                    generated_views.append(gen_view(members, joints, filename, 'bottom', options))
            
            export_views_to_obj(generated_views, filename, options)
            logging.info("File successfully converted")
            logging.info("Starting write process...")
            
            

        else:
            logging.error("invalid file type")
            return
    folder_path = os.path.realpath(dest_dir.get())
    os.startfile(folder_path)
    return





def main()->None:
    logging.info("Starting RISA-3D to OBJ Converter")
    
    # Select/return filepath(s). Also updates the label displayed next to the "Select" button in the GUI.
    def file_select(file,file_label):
        selected_file = filedialog.askopenfilename(
            multiple=TRUE,   # Allow multiple files to be selected.
            filetypes=[("RISA/Modelsmart Files", "*.3dd *.r3d"), ("All Files", "*.*")]   # Limit searchable files to those with .3dd or .r3d extensions
        )
        if selected_file:
            if len(selected_file) > 1:
                file_list = []
                file_string = ''
                for i in selected_file:
                    file_list.append(i)
                    file_string += i
                    if i != selected_file[len(selected_file) - 1]:
                        file_string += '\n'
                file_label.config(text=file_string)
            else:
                file_list = selected_file[0]
                file_label.config(text=selected_file[0])
            file.set(file_list)

    # Select/return the destination directory that the converted files will be saved to.
    def dest_select(dest_dir, dest_label):
        selected_dest = filedialog.askdirectory()
        if selected_dest:
            dest_label.config(text=selected_dest)
            dest_dir.set(selected_dest)

    # Advanced settings sub-page is in a callable function that is called when the user clicks on the "Advanced" button.
    def Advanced_Settings():
        adv_x = root.winfo_x() + 120
        adv_y = root.winfo_y() + 60
        advanced = Toplevel(root, takefocus=1)
        advanced.geometry(f"+{adv_x}+{adv_y}")
        advanced.grab_set()
        advanced.title("Advanced Settings")
        advframe = ttk.Frame(advanced, padding="3 3 12 12")
        advframe.grid(column=0, row=0, sticky=(N, W, E, S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        ttk.Label(advframe, text="Advanced Settings", font=("Arial", 13)).grid(column=0, row = 0, padx=(25,25), pady=(5,5))

        # 2D View Options Section.
        dim_options_label = ttk.Label(advframe, text="Advanced 2D Options", foreground="black")
        dim_options_frame = ttk.Frame(advframe)
        side_button = ttk.Checkbutton(dim_options_frame, text="Side", variable=side, onvalue=True, offvalue=False)
        top_button = ttk.Checkbutton(dim_options_frame, text="Top", variable=top, onvalue=True, offvalue=False)
        bottom_button = ttk.Checkbutton(dim_options_frame, text="Bottom", variable=bottom, onvalue=True, offvalue=False)
        dim_options_label.grid(column=0, row=1, padx=(0,0), pady=(5,0))
        side_button.grid(column=0, row=0, padx=(10,10))
        top_button.grid(column=1, row=0, padx=(10,10))
        bottom_button.grid(column=2, row=0, padx=(10,0))
        dim_options_frame.grid(column=0, row=2, padx=(0,0), pady=(5,6))
        ToolTip(dim_options_label, msg="Specify which 2D views you'd like generated.\nDefault is all of them.", delay=0.5)

        misc_options_frame = ttk.Frame(advframe)

        # Cylinder Options Section.
        cyl_options_label = ttk.Label(misc_options_frame, text='Cylinder Detail:', foreground="black")
        cyl_options_field = ttk.Entry(misc_options_frame, textvariable=cyl_vert, justify=LEFT, width=4)
        cyl_options_label.grid(column=0, row=0, padx=(0,5), pady=(5,5), sticky=E)
        cyl_options_field.grid(column=1, row=0, padx=(2,0), pady=(5,5), sticky=W)
        ToolTip(cyl_options_label, msg="Number of side faces for generated cylinders.\nThe more faces, the closer they will be to an actual cylinder.\nDefault is 16.", delay=0.5, follow=True)

        # Coordinate Precision Section.
        prec_options_label = ttk.Label(misc_options_frame, text='Coordinate Precision:', foreground="black")
        prec_options_field = ttk.Entry(misc_options_frame, textvariable=coord_prec, justify=LEFT, width=4)
        prec_options_label.grid(column=0, row=1, padx=(0,5), pady=(5,5), sticky=E)
        prec_options_field.grid(column=1, row=1, padx=(2,0), pady=(5,5), sticky=W)
        ToolTip(prec_options_label, msg="Number of decimal places to round to.\nDefault is 3 (thousandths).", delay=0.5, follow=True)

        # File Creation Options Section.
        folder_options_label = ttk.Label(misc_options_frame, text='Subfolder Creation:', foreground="black")
        folder_options_button = ttk.Checkbutton(misc_options_frame, variable=folder_opt, onvalue=True, offvalue=False)
        folder_options_label.grid(column=0, row=2, padx=(0,5), pady=(5,5), sticky=E)
        folder_options_button.grid(column=1, row=2, padx=(0,0), pady=(5,5), sticky=W)
        ToolTip(folder_options_label, msg="Choose whether you'd like the models to be placed in unique subfolders.\nDefault is enabled.", delay=0.5, follow=True)
        
        misc_options_frame.grid(column=0, row=3, padx=(0,0), pady=(0,0))

        exit_button = ttk.Button(advframe, text="Exit", command=lambda: advanced.destroy(), width=5)
        exit_button.grid(column=0, row=10, sticky=E)
        advanced.mainloop()
    

    root = Tk()
    root.title("RISA-3D to OBJ Converter")
    root.resizable(False, False)
    style = ttk.Style(root)
    style.configure('UFrame', background=BACKGROUND_COLOR, foreground='black')
    style.configure('TFrame', background=BACKGROUND_COLOR, foreground='black')
    style.configure('TLabel', background=BACKGROUND_COLOR, foreground='black')
    style.configure('TCheckbutton', background=BACKGROUND_COLOR, foreground='black')
    mainframe = ttk.Frame(root, padding="3 3 12 12")
    mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    
    file = StringVar(value=[])
    dim_var = StringVar(value='All')
    side = BooleanVar(value=True)
    top = BooleanVar(value=True)
    bottom = BooleanVar(value=True)
    cyl_vert = StringVar(value="16")
    coord_prec = StringVar(value="3")
    dest_dir = StringVar(value=os.getcwd())
    folder_opt = BooleanVar(value=True)
    

    main_title = ttk.Label(mainframe, text="UAA 3D File Conversion Tool", font=("Arial", 15))
    main_title.grid(column=0, row=0, padx=(0,0), pady=(5,10))
    
    file_title = ttk.Label(mainframe, text="Source File(s)", font=("Arial", 10))
    file_frame = ttk.Frame(mainframe)
    file_button = ttk.Button(file_frame, text="Select", command=lambda: file_select(file,file_label), width=7)
    file_label = ttk.Label(file_frame, text="", background="white", relief='sunken', width=50, wraplength=300)
    file_title.grid(column=0, row=1, padx=(25,25), pady=(0,0))
    file_button.grid(column=0, row=0, sticky = 'W')
    file_label.grid(column=1, row=0, padx=(5,0), pady=(0,0))
    file_frame.grid(column=0, row=2, padx=(25,25), pady=(5,10))
    ToolTip(file_title, msg="Select the file(s) you'd like to convert.", delay=0.5, follow=True)

    dest_title = ttk.Label(mainframe, text="Destination Folder", font=("Arial", 10))
    dest_frame = ttk.Frame(mainframe)
    dest_button = ttk.Button(dest_frame, text="Select", command=lambda: dest_select(dest_dir,dest_label), width=7)
    dest_label = ttk.Label(dest_frame, text=dest_dir.get(), background="white", relief='sunken', width=50, wraplength=300)
    dest_title.grid(column=0, row=3, padx=(25,25), pady=(5,0))
    dest_button.grid(column=0, row=0, sticky = 'W')
    dest_label.grid(column=1, row=0, padx=(5,0), pady=(0,0))
    dest_frame.grid(column=0, row=4, padx=(10,10), pady=(5,10))
    ToolTip(dest_title, msg="Select the directory where you'd like the converted files created.", delay=0.5, follow=True)
    
    dim_frame = ttk.Frame(mainframe)
    dim_label = ttk.Label(dim_frame, text="2D/3D Views:", foreground="black")
    dim_box = ttk.Combobox(dim_frame, textvariable=dim_var, width=4)   
    dim_box['values'] = ('2D', '3D','All')
    dim_box.state(["readonly"])
    dim_label.grid(column=0, row=0, padx=(0,10), pady=(0,0))
    dim_box.grid(column=1, row=0, padx=(0,0), pady=(0,0))
    dim_frame.grid(column=0, row=5, padx=(0,0), pady=(10,10))
    ToolTip(dim_label, msg="Choose between only 2D views, only 3D views, or all views.\nAdditional 2D options are available in the Advanced menu.", delay=0.25)

    bottom_frame = ttk.Frame(mainframe)
    advanced_button = ttk.Button(bottom_frame, text="Advanced", command = lambda: Advanced_Settings(), width=10)
    convert_button = ttk.Button(bottom_frame, text="Convert", command =lambda: convert(file, dest_dir, dim_var, side, top, bottom, cyl_vert, coord_prec), width=9)
    exit_button = ttk.Button(bottom_frame, text="Exit", command=root.destroy, width=5)
    advanced_button.grid(column=0, row=0, padx=(0,20), pady=(0,0), sticky=W)
    convert_button.grid(column=1, row=0, padx=(20,20), pady=(0,0))
    exit_button.grid(column=2, row=0, padx=(20,0), pady=(0,0), sticky=E)
    bottom_frame.grid(column=0, row=6, padx=(10,0), pady=(10,5))

    root.mainloop()


if __name__=="__main__":
    main()