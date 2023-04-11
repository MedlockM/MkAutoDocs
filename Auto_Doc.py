import openai
import yaml
import os
from pathlib import Path
import re
from dotenv import load_dotenv

#load configuration
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
with open("./Auto_Doc_config.yml", "r") as f:
    config = yaml.safe_load(f)


def chat_completion(user:str, system:str, model:str="gpt-3.5-turbo", temperature=None, max_tokens=None)->openai.ChatCompletion.create:
    messages = [
        {
            "role": "system",
            "content": system,
        },
        {"role": "user", "content": user},
    ]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response

def folder_structure(path:str) -> dict:
    """
    Returns a dictionary of file and folder structure from a given folder.
    """
    if not os.path.isdir(path):
        raise ValueError(f"{path} is not a valid directory")

    structure = {"folders": {}, "files": []}
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            structure["files"].append(item_path)
        elif os.path.isdir(item_path):
            structure["folders"][item_path] = folder_structure(item_path)

    return structure

def write_md_documentation(code: str) -> str:
    system = """You are a helpful documentation generation bot, you take in code and return a string value a string of MDTest formatted markdown with details about the code with examples"""
    result = chat_completion(code, system)
    return result.choices[0].message["content"]

def make_dir(path):
    print("Running mkdir")
    p = Path(path)
    if not p.exists():
        print(f"Creating folder {path}")
    p.mkdir(exist_ok=True, parents=True)

def ignore_checks(path_string, ignore_regexes):
    for regex in ignore_regexes:
        if re.search(regex, path_string):
            return True
    return False

def ignore_files(path_string:str):
    return ignore_checks(path_string, config.get("ignore_files", []))

def ignore_folders(path_string:str):
    return ignore_checks(path_string, config.get("ignore_folders", []))

def make_save_folder(folder:str, root_dir:str, docs_path:str):
    rel_path = os.path.relpath(folder, root_dir)
    return Path(f"{root_dir}/{docs_path}") / rel_path
    
def get_file_documentation(files:list, save_path:Path)-> None:
    make_dir(save_path)
    for file in files:
        if ignore_files(file):
            continue
        file_name = Path(file).stem
        doc_file_path = save_path / f"{file_name}.md"
        if doc_file_path.as_posix() in already_parsed:
            print(f"File {file_name}.md already generated, turn off state to regenerate all files.")
            continue
        text = Path(file).read_text()
        print(f"Getting documentation for file {doc_file_path}")
        doc_file_path.write_text(write_md_documentation(text))
        
def get_markdown(source_folder_dir:dir, save_folder:Path, root_doc:str, docs_path:str):
    files = source_folder_dir.get("files", [])
    get_file_documentation(files, save_folder)
    folders = source_folder_dir.get("folders", {})
    for key, value in folders.items():
        if ignore_folders(key):
            continue
        save_folder = make_save_folder(key, root_doc, docs_path)
        get_markdown(value, save_folder, root_doc, docs_path)

def build_state(docs_folder_path):
    file_set = set()
    for foldername, subfolders, filenames in os.walk(docs_folder_path):
        # Loop through the filenames
        for filename in filenames:
            # Get the full path of the file
            file_path = Path(foldername, filename).as_posix()
            # Add the file path to the set
            file_set.add(file_path)
    return file_set

def make_mkdocs_yaml(root_dir:str)-> None:
    p = Path(f"{root_dir}/mkdocs.yml")
    if p.exists():
        print("mkdocs file already exists, not altering")
        return
    print("Creating mkdocs.yml in root dir")
    mkdocs = config.get("mkdocs", {})
    p.write_text(yaml.safe_dump(mkdocs, sort_keys=False))

def update_requirements(requirement: str, version: str, file_path: str = "requirements.txt")-> None:
    # Read in the requirements file
    if not Path(file_path).exists():
        print("creating requirements.txt")
        Path(file_path).write_text("")
    with open(file_path, "r") as f:
        requirements = f.readlines()
    # Check if the requirement is already present and at the correct version
    for i, req in enumerate(requirements):
        if req.startswith(requirement):
            if f"=={version}" in req:
                print(f"{requirement} is already at version {version}")
                return

            # Update the requirement to the correct version
            requirements[i] = f"{requirement}=={version}\n"
            with open(file_path, "w") as f:
                f.writelines(requirements)
            print(f"Updated {requirement} to version {version}")
            return

    # If the requirement is not present, add it to the file
    requirements.append(f"{requirement}=={version}\n")
    with open(file_path, "w") as f:
        f.writelines(requirements)
    print(f"Added {requirement} version {version} to requirements.txt")

def make_mkdocs_documents():
    print("Loading config")
    root_dir, docs_path, source_to_document, use_state = config.get("root_dir"), config.get("docs_path"), config.get("source_to_document"), config.get("use_state")
    global already_parsed
    root_and_docs_path = Path(f"{root_dir}/{docs_path}")
    already_parsed = build_state(root_and_docs_path) if use_state else set()
    print(f"Loaded state for {len(already_parsed)} files")
    for source_dir in source_to_document:
        
        source_folder_dir = folder_structure(source_dir)
        get_markdown(source_folder_dir, root_and_docs_path, root_dir, docs_path)
    make_mkdocs_yaml(root_dir)
    print("Building requirments.txt")
    for requirment in config.get("requirements"):
        if not isinstance(requirment, dict):
            print("Warning, all requirements need to be key value pairs")
            continue
        package, version = next(iter(requirment.items()))
        update_requirements(package, version, f"{root_dir}/requirements.txt")
        

if __name__ == "__main__":
    make_mkdocs_documents()