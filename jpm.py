import argparse
from pathlib import Path
import sys
import requests
import xml.etree.ElementTree as ET
import subprocess
import os
import zipfile
import io
import questionary
import zipfile
import io
from utils.helpers import get_pom_content, get_pom_tree, get_version_info, load_jproject, save_jproject, save_pom, MAVEN_NS, SEARCH_URL, get_spring_metadata, get_cached_spring_metadata, cache_spring_metadata, get_main_class_content, get_test_class_content

'''
JPM: Java Package Manager (Maven Wrapper)
A simple CLI tool to manage creating Java projects, installing dependencies, and running code without needing to write XML or use Maven commands directly.
'''

BASE_DIR = Path(__file__).resolve().parent

# For windows
if os.name == "nt":
    MAVEN_WRAPPER_PATH = BASE_DIR / "mvnw.cmd"
else:  # For macOS/Linux
    MAVEN_WRAPPER_PATH = BASE_DIR / "mvnw"


def cmd_setup(args):
    print("⚙️  Setting up JPM...")
    try:
        subprocess.run(
            ["java", "-version"],
            shell=True,
            check=True
        )
        print("✅ Java is installed.")

        subprocess.run(
            [str(MAVEN_WRAPPER_PATH), "-version"],
            shell=True,
            check=True
        )
        print("✅ Maven is ready to use with JPM!")

    except subprocess.CalledProcessError as e:
        print("❌ Setup failed.")
        print(e)


def cmd_init(args):
    proj_type = questionary.select(
        "Select project type:",
        choices=[
            {"name": "🍵 Standard Java Project", "value": "standard-java-project"},
            {"name": "🍃 Spring Boot Project", "value": "spring-boot-project"}
        ]
    ).ask()
    print(f"Selected: {proj_type.replace('-', ' ').title()}")
    if proj_type == "spring-boot-project":
        init_spring_boot(args)
    elif proj_type == "standard-java-project":
        init_standard_java(args)


def init_spring_boot(args):
    print("🍃 Initializing new Spring Boot project...")

    # 1. Selection using Arrow Keys
    boot_version = questionary.select(
        "Select Spring Boot Version:",
        choices=["3.5.10", "3.5.11-SNAPSHOT", "4.0.2", "4.1.0-M1"],
        default="4.0.2"
    ).ask()

    # 2. Checklist for Dependencies (Press Space to select)
    deps_list = questionary.checkbox(
        "Select Dependencies (Space to select, Enter to confirm):",
        choices=[
            {"name": "Spring Web", "value": "web"},
            {"name": "Spring Data JPA", "value": "data-jpa"},
            {"name": "MySQL Driver", "value": "mysql"},
            {"name": "Lombok", "value": "lombok"},
            {"name": "Spring Security", "value": "security"},
            {"name": "Validation", "value": "validation"},
            {"name": "Spring Boot DevTools", "value": "devtools"},
            {"name": "Eureka Discovery Client",
             "value": "cloud-eureka"},
            {"name": "Eureka Server",
             "value": "cloud-eureka-server"},
            {"name": "OpenFeign",
             "value": "cloud-feign"},
            {"name": "Spring Cloud Gateway",
             "value": "cloud-gateway"},
        ]
    ).ask()

    # Convert list to comma-separated string for the API
    deps = ",".join(deps_list)

    # 3. Standard text inputs
    group_id = questionary.text("Group ID:", default="com.example").ask()
    artifact_id = questionary.text("Artifact ID:", default="demo").ask()
    java_version = questionary.select("Java Version:", choices=[
                                      "21", "17", "11"], default="17").ask()

    # 4. Fetch Metadata to cache valid aliases
    print("🌍 Fetching Spring Metadata...")
    meta_deps = get_spring_metadata()

    if not meta_deps:
        print("❌ Failed to fetch Spring metadata. Please check your network connection.")
        return

    cache_spring_metadata(meta_deps, artifact_id)

    # 5. Initialize and store jproject.json
    jproject_data = {
        "projectType": "spring-boot",
        "springBootVersion": boot_version,
        "groupId": group_id,
        "artifactId": artifact_id,
        "version": "0.0.1-SNAPSHOT",
        "javaVersion": java_version,
        "mainClass": f"{group_id}.{artifact_id}.{artifact_id.capitalize()}Application",
        # e.g. ['web', 'data-jpa']
        "starterDependencies": deps.split(",") if deps else [],
        "dependencies": []  # e.g. ['com.google.code.gson:gson:2.10.1']
    }
    save_jproject(jproject_data, artifact_id)

    # 6. Call Spring Initializr API to generate project
    params = {
        "type": "maven-project",
        "language": "java",
        "bootVersion": boot_version,
        "baseDir": artifact_id,
        "groupId": group_id,
        "artifactId": artifact_id,
        "name": artifact_id,
        "javaVersion": java_version,
        "dependencies": deps
    }

    url = "https://start.spring.io/starter.zip"

    try:
        print(f"🚚 Downloading {artifact_id}...")
        response = requests.get(url, params=params)

        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(".")

            print(f"\n✨ Spring Boot project '{artifact_id}' is ready!")
            print(f"👉 cd {artifact_id} && jpm run")
        else:
            print(f"❌ API Error: {response.text}")

    except Exception as e:
        print("❌ Failed to initialize Spring Boot project.")
        print(f"❌ Error: {e}")


def init_standard_java(args):
    print("🚀 Initializing new Java project...")

    # Configuration
    try:
        group_id = questionary.text("Group ID:", default="com.example").ask()
        artifact_id = questionary.text("Artifact ID:", default="demo").ask()
        version = questionary.text("Version:", default="1.0-SNAPSHOT").ask()

        java_version = questionary.select("Java Version:", choices=[
                                          "21", "17", "11"], default="21").ask()

        # 1. Define the directory structure
        dirs = [
            f"{artifact_id}/src/main/java/{group_id.replace('.', '/')}",
            f"{artifact_id}/src/test/java/{group_id.replace('.', '/')}"
        ]

        # 2. Define the Modern POM (Java 21 + JUnit 5)
        pom_content = get_pom_content(
            group_id, artifact_id, version, java_version)

        # 3. Create Directories
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        # 4. Write POM
        with open(f"{artifact_id}/pom.xml", "w", encoding="utf-8") as f:
            f.write(pom_content)

        # 5. Create Main Class
        main_class_content = get_main_class_content(group_id)
        with open(f"{artifact_id}/src/main/java/{group_id.replace('.', '/')}/App.java", "w", encoding="utf-8") as f:
            f.write(main_class_content)

        # Test Class
        test_class_content = get_test_class_content(group_id)

        with open(f"{artifact_id}/src/test/java/{group_id.replace('.', '/')}/AppTest.java", "w", encoding="utf-8") as f:
            f.write(test_class_content)

        # Initialize and store jproject.json
        jproject_data = {
            "projectType": "standard-java",
            "groupId": group_id,
            "artifactId": artifact_id,
            "javaVersion": java_version,
            "version": version,
            "mainClass": f"{group_id}.App",
            "dependencies": []  # e.g. ['com.google.code.gson:gson:2.10.1']
        }
        save_jproject(jproject_data, artifact_id)

        print(f"\n✨ Project created: {artifact_id}")
        print(f"👉 cd {artifact_id} && jpm run")

    except Exception as e:
        print("❌ `jpm init` failed.")
        print(f"❌ Error: {e}")


def cmd_install(args):
    query = args.package
    g, a, v = None, None, None

    tree = get_pom_tree()
    root = tree.getroot()
    ns = {'m': MAVEN_NS}

    jproject = load_jproject()

    # If it's a Spring Boot project, we check if the query matches any known Spring Boot starter alias
    if jproject and jproject["projectType"] == 'spring-boot':
        spring_cache = get_cached_spring_metadata()
        if query in spring_cache:
            print(f"🍃 Detected Spring Boot Starter: {spring_cache[query]}")
            install_spring_dep(query, jproject)
            return

    # Else, we proceed with standard Maven Central search and install logic
    # 1. Parse Input (g:a:v, g:a, or query)
    if ":" in query:
        parts = query.split(":")
        if len(parts) == 3:
            g, a, v = parts
        elif len(parts) == 2:
            g, a = parts

    print(f"🔍 Searching Maven Central for '{query}'...")

    # 2. Build Search Parameter
    if g and a:
        if v:
            search_param = f'g:"{g}" AND a:"{a}" AND v:"{v}"'
        else:
            search_param = f'g:"{g}" AND a:"{a}"'
    else:
        search_param = query

    # 3. Fetch from Maven Central
    # Fetch multiple results (up to 10) if only query is provided
    rows = 1 if (g and a) else 10
    params = {'q': search_param, 'rows': rows, 'wt': 'json'}
    try:
        response = requests.get(SEARCH_URL, params=params, verify=True)
        data = response.json()
        if data['response']['numFound'] == 0:
            print(f"❌ Package not found: {query}")
            return

        docs = data['response']['docs']

        # If multiple results and user didn't specify full g:a, let them choose
        if len(docs) > 1 and not (g and a):
            print(f"\n📦 Found {len(docs)} packages:")
            choices = []
            for doc in docs:
                dep_str = f"{doc['g']}:{doc['a']}:{doc.get('latestVersion') or doc.get('v')}"
                choices.append({"name": dep_str, "value": (doc['g'], doc['a'], doc.get(
                    'latestVersion') or doc.get('v'), doc.get("p") or "jar")})

            selected = questionary.select(
                "Select the dependency to install:",
                choices=choices
            ).ask()

            if selected is None:
                print("❌ No selection made.")
                return

            g, a, v, p = selected
            print(f"\n✅ Selected: {g}:{a}:{v}")
        else:
            # Single result or full g:a specified
            doc = docs[0]
            g = g or doc['g']
            a = a or doc['a']
            v = v or doc.get('latestVersion') or doc.get(
                'v')  # Use found version if none provided
            p = p or doc.get("p") or "jar"

            print(f"✅ Found: {g}:{a}:{v}")
    except Exception as e:
        print(f"❌ Network error: {e}")
        return

    # 4. Update XML
    deps_tag = root.find('m:dependencies', ns)
    if deps_tag is None:
        deps_tag = ET.SubElement(root, f"{{{MAVEN_NS}}}dependencies")

    found = False
    for dep in deps_tag.findall('m:dependency', ns):
        if dep.find('m:artifactId', ns).text == a and dep.find('m:groupId', ns).text == g and dep.find('m:version', ns).text == v:
            print("🧐 Dependency already exists in pom.xml")
            return
        if dep.find('m:artifactId', ns).text == a and dep.find('m:groupId', ns).text == g:
            dep.find('m:version', ns).text = v
            found = True
            print(f"🔄 Updated existing dependency to {v}")
            break

    if not found:
        new_dep = ET.SubElement(deps_tag, f"{{{MAVEN_NS}}}dependency")
        ET.SubElement(new_dep, f"{{{MAVEN_NS}}}groupId").text = g
        ET.SubElement(new_dep, f"{{{MAVEN_NS}}}artifactId").text = a
        ET.SubElement(new_dep, f"{{{MAVEN_NS}}}version").text = v
        if p != "jar":
            ET.SubElement(new_dep, f"{{{MAVEN_NS}}}type").text = p

    # 5. Save and Download
    save_pom(tree)

    # 6. Update jproject.json deps list
    if jproject:
        dep_entry = {
            "groupId": g,
            "artifactId": a,
            "version": v,
            "type": p
        }
        if dep_entry not in jproject["dependencies"]:
            jproject["dependencies"].append(dep_entry)
            save_jproject(jproject)
    else:
        print("⚠️  Warning: jproject.json not found. Dependency added to pom.xml but not tracked in jproject state.")

    print("⌛ Downloading JARs...")
    try:
        # -q (Quiet), -B (Batch), -ntp (No Transfer Progress)
        subprocess.run([str(MAVEN_WRAPPER_PATH), "dependency:resolve", "-q",
                       "-B", "-ntp"], check=True, shell=True)
        print("✅ Dependencies ready.")
    except subprocess.CalledProcessError:
        print("❌ Maven failed to download JARs. Check your pom.xml.")


def cmd_uninstall(args):
    """
    Removes a dependency from pom.xml by Artifact ID.
    """
    target = args.package
    print(f"🗑️  Uninstalling '{target}'...")

    tree = get_pom_tree()
    root = tree.getroot()
    ns = {'m': MAVEN_NS}

    jproject = load_jproject()

    if ":" in target:
        parts = target.split(":")
        if len(parts) == 3:
            g, a, v = parts
        elif len(parts) == 2:
            g, a = parts

    # Look for the custom property we saved during init
    proj_type = jproject.get("projectType")

    if jproject:
        if proj_type == 'spring-boot':
            # Handles -> 1. Direct starter alias match (e.g. 'web')
            jproject["starterDependencies"] = [
                d for d in jproject["starterDependencies"] if d != target]

            # Handles -> 2. Full artifact match, if user provides groupId:artifactId (e.g. 'org.springframework:spring-boot-starter-web')
            if a and a.replace("spring-boot-starter-", "") in jproject["starterDependencies"]:
                jproject["starterDependencies"] = [
                    d for d in jproject["starterDependencies"] if d != a.replace("spring-boot-starter-", "")]

            # Handles -> 3. If user tries to uninstall using full starter artifact (e.g. 'spring-boot-starter-web'), we also check if the alias ('web') is in the list and remove it
            elif target.startswith("spring-boot-starter-") and target.replace("spring-boot-starter-", "") in jproject["starterDependencies"]:
                jproject["starterDependencies"] = [
                    d for d in jproject["starterDependencies"] if d != target.replace("spring-boot-starter-", "")]

        # For normal dependencies (non-starter), we match by groupId and artifactId if provided, else just artifactId
        if g and a:
            jproject["dependencies"] = [d for d in jproject["dependencies"]
                                        if d["groupId"] != g or d["artifactId"] != a]
        else:
            jproject["dependencies"] = [
                d for d in jproject["dependencies"] if d["artifactId"] != target]
        save_jproject(jproject)

    else:
        print("⚠️  Warning: jproject.json not found. Uninstalling from pom.xml but jproject state may be out of sync.")

    dependencies = root.find('m:dependencies', ns)
    if dependencies is None:
        print("❌ No dependencies found in pom.xml")
        return

    found = False
    for dep in dependencies.findall('m:dependency', ns):
        g_id = dep.find('m:groupId', ns).text
        a_id = dep.find('m:artifactId', ns).text

        if g and a:
            if g_id == g and a_id == a:
                dependencies.remove(dep)
                found = True
                print(
                    f"🔥 Removed dependency: {g_id}:{a_id}:{dep.find('m:version', ns).text}")
                break  # Remove only first match for safety
        else:
            # Simple match: if the artifact ID contains the search string
            if a_id.lower() in target.lower():
                dependencies.remove(dep)
                found = True
                print(
                    f"🔥 Removed dependency: {dep.find('m:groupId', ns).text}:{dep.find('m:artifactId', ns).text}:{dep.find('m:version', ns).text}")
                break  # Remove only first match for safety

    if found:
        print("⌛ Cleaning up project state...")
        try:
            # This triggers Maven to clean the project
            subprocess.run([str(MAVEN_WRAPPER_PATH), "clean",
                           "-q"], check=True, shell=True)
            print("✅ Project cleaned successfully.")
            save_pom(tree)
        except subprocess.CalledProcessError:
            print("❌ Maven failed to clean project.")
            return
    else:
        print(f"❌ Could not find package '{target}' in pom.xml")
        return


def cmd_run(args):
    """Reads mainClass from jproject.json and executes it."""

    print(f"🛠️  Compiling and executing your code ...")

    jproject = load_jproject()

    if jproject and jproject["projectType"] == 'spring-boot':
        print("🍃 Starting Spring Boot Application...")
        cmd = [str(MAVEN_WRAPPER_PATH), "spring-boot:run", "-q", "-B"]
    else:
        # Look for the custom property we saved during init
        main_class = jproject.get("mainClass") if jproject else None

        if not main_class:
            print("❌ Error: Could not find <mainClass> property in pom.xml.")
            print("💡 Add <mainClass>your.package.Main</mainClass> to <properties>.")
            return

        if not os.path.exists(f"src/main/java/{main_class.replace('.', '/')}.java"):
            print(
                f"❌ Error: Main class file not found at src/main/java/{main_class.replace('.', '/')}.java")
            return

        print(f"🚀 Running {main_class.split('.')[-1]}.java ...")
        # Execute using Maven
        # -q keeps it clean, -B for batch mode
        cmd = [str(MAVEN_WRAPPER_PATH), "compile", "exec:java",
               f"-Dexec.mainClass={main_class}", "-q", "-B"]

    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        print("\n❌ Runtime error or compilation failed.")


def cmd_clean(args):
    """
    Removes the target folder to clean compiled files.
    """
    print("🧹 Cleaning project...")
    try:
        subprocess.run([str(MAVEN_WRAPPER_PATH), "clean", "-q"],
                       check=True, shell=True)
        print("✅ Project cleaned successfully.")
    except subprocess.CalledProcessError:
        print("❌ Failed to clean project.")
        return


def cmd_build(args):
    """
    Builds the project (compiles and packages).
    """
    print("🏗️  Building project...")
    try:
        subprocess.run([str(MAVEN_WRAPPER_PATH), "clean", "package",
                       "-q"], check=True, shell=True)
        print("✅ Project built successfully.")
    except subprocess.CalledProcessError:
        print("❌ Build failed.")
        return


def cmd_sync(args):
    """
    Syncs/Installs dependencies in pom.xml with the local repository.
    """
    print("🔄 Syncing dependencies...")
    try:
        subprocess.run([str(MAVEN_WRAPPER_PATH), "dependency:resolve", "-q"],
                       check=True, shell=True)
        print("✅ Dependencies synced successfully.")
    except subprocess.CalledProcessError:
        print("❌ Failed to sync dependencies.")
        return


def cmd_test(args):
    """
    Runs tests using Maven.
    """
    print("🧪 Running tests...")
    try:
        subprocess.run([str(MAVEN_WRAPPER_PATH), "clean",
                       "test", "-B"], check=True, shell=True)
        print("✅ Tests completed.")
    except subprocess.CalledProcessError:
        print("❌ Tests failed.")
        return


def install_spring_dep(new_dep, jproject):
    """
    The Re-hydration Strategy:
    1. Add new dep to list.
    2. Ask Spring for a fresh ZIP.
    3. Extract POM, replace old POM.
    4. Inject 'normal' deps into new POM.
    """
    if new_dep in jproject["starterDependencies"]:
        print("⚠️  Dependency already exists in Spring configuration.")
        return

    # 1. Update State
    jproject["starterDependencies"].append(new_dep)
    print(f"🔃 Getting your dependency '{new_dep}' from Spring Initializr...")

    # 2. Build API Request
    params = {
        "type": "maven-project",
        "language": "java",
        "bootVersion": jproject["springBootVersion"],
        "baseDir": jproject["artifactId"],
        "groupId": jproject["groupId"],
        "artifactId": jproject["artifactId"],
        "name": jproject["artifactId"],
        "javaVersion": jproject["javaVersion"],
        "dependencies": ",".join(jproject["starterDependencies"])
    }

    try:
        url = "https://start.spring.io/starter.zip"
        print("☁️  Contacting start.spring.io...")
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print("❌ Failed to fetch update from Spring.")
            return

        # 3. Safe Extraction
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # We are looking for 'pom.xml' inside the nested folder
            # The zip usually has structure: artifactId/pom.xml
            pom_path = f"{jproject['artifactId']}/pom.xml"

            if pom_path not in z.namelist():
                # Fallback if structure is flat
                pom_path = "pom.xml"

            # Read the NEW generated POM
            with z.open(pom_path) as f:
                new_pom_content = f.read()

            # Extract other files safely (to check for new files, after the dependency addition)

            for file_info in z.infolist():
                # Strip the root folder name (artifactId/)
                filename = file_info.filename

                if filename.startswith(jproject['artifactId'] + "/"):
                    target_name = filename.split("/", 1)[1]
                else:
                    target_name = filename

                # SKIP LIST: Don't overwrite these!
                if target_name.startswith("src/main/java"):
                    continue
                if target_name.startswith("src/test/java"):
                    continue
                if target_name == "pom.xml":
                    continue  # We handle this manually

                # SAFE LIST: Only write if it doesn't exist
                # e.g., src/main/resources/application.properties
                if os.path.exists(target_name):
                    continue

                # If it's a new file/folder (like a new config file for a dependency), add it
                if target_name:
                    if file_info.is_dir():
                        print(f"📁 Adding new folder: {target_name}")
                        os.makedirs(target_name, exist_ok=True)
                    else:
                        print(f"📄 Adding new file: {target_name}")
                        os.makedirs(os.path.dirname(
                            target_name), exist_ok=True)
                        with open(target_name, "wb") as f:
                            f.write(z.read(file_info))

        # 4. Parse the NEW POM
        new_root = ET.fromstring(new_pom_content)
        ET.register_namespace('', MAVEN_NS)

        # 5. Inject Normal Dependencies (The ones not managed by Spring)
        # These are stored in our jproject.json "dependencies" key
        if jproject["dependencies"]:
            print("💉 Injecting other dependencies...")
            ns = {'m': MAVEN_NS}
            deps_tag = new_root.find('m:dependencies', ns)

            for dep in jproject["dependencies"]:
                # dep format: {"groupId": g, "artifactId": a, "version": v, "type": p}
                g = dep.get("groupId")
                a = dep.get("artifactId")
                v = dep.get("version")
                p = dep.get("type", "jar")

                # Create Element
                d_elem = ET.SubElement(deps_tag, f"{{{MAVEN_NS}}}dependency")
                ET.SubElement(d_elem, f"{{{MAVEN_NS}}}groupId").text = g
                ET.SubElement(d_elem, f"{{{MAVEN_NS}}}artifactId").text = a
                ET.SubElement(d_elem, f"{{{MAVEN_NS}}}version").text = v
                if p != "jar":
                    ET.SubElement(d_elem, f"{{{MAVEN_NS}}}type").text = p

        # 6. Save State and File
        save_jproject(jproject)

        # Write the new POM to disk (Overwriting the old one)
        tree = ET.ElementTree(new_root)
        save_pom(tree)

        # 7. Sync
        cmd_sync(None)

    except Exception as e:
        print(f"❌ Error during re-hydration: {e}")

# --- CLI Setup ---


def main():
    parser = argparse.ArgumentParser(
        description="JPM: Java Package Manager (Maven Wrapper)")

    # Version
    if len(sys.argv) > 1 and sys.argv[1] in ["-v", "--version"]:
        # print(f"📦 JPM Version {VERSION}")
        print(get_version_info())
        return

    subparsers = parser.add_subparsers(dest="command", required=True)
    # Setup (for first-time setup, like checking Java installation and downloading Maven Wrapper)
    subparsers.add_parser(
        "setup", help="Setup JPM for the first time (check Java, download Maven Wrapper)")

    # Init
    subparsers.add_parser("init", help="Initialize a new Java project")

    # Install
    parser_install = subparsers.add_parser(
        "install", help="Install a dependency")
    parser_install.add_argument(
        "package", help="Name of the package (e.g. 'jackson', 'junit')")

    # Uninstall
    parser_uninstall = subparsers.add_parser(
        "uninstall", help="Remove a dependency")
    parser_uninstall.add_argument(
        "package", help="Artifact ID of the package to remove")

    # Run
    subparsers.add_parser("run", help="Compile and run the project")

    # Clean
    subparsers.add_parser("clean", help="Clean the project")

    # Sync
    subparsers.add_parser("sync", help="Sync dependencies")

    # Build
    subparsers.add_parser("build", help="Build the project")

    # Test
    subparsers.add_parser("test", help="Run tests")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "install" or args.command == "i":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "test":
        cmd_test(args)


if __name__ == "__main__":
    main()
