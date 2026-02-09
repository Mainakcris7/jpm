import platform
import subprocess
import xml.etree.ElementTree as ET
import os
import sys
import json
import requests

# Maven Central Search API
SEARCH_URL = "https://search.maven.org/solrsearch/select"
MAVEN_NS = "http://maven.apache.org/POM/4.0.0"

VERSION = "1.0.1"
VERSION_DATE = "2026-02-09"

JPM_DIR = ".jpm"
JPROJECT_FILE = os.path.join(JPM_DIR, "jproject.json")
SPRING_CACHE_FILE = os.path.join(JPM_DIR, "spring_metadata.json")

# --- Helper Functions ---


def indent(elem, level=0):
    """
    Adds indentation to the XML tree so the output pom.xml 
    is human-readable (pretty-printed).
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def get_pom_tree():
    """Parses the pom.xml file in the current directory."""
    if not os.path.exists("pom.xml"):
        print("❌ Error: No pom.xml found. Run 'jpm init' first.")
        sys.exit(1)

    ET.register_namespace('', MAVEN_NS)
    return ET.parse("pom.xml")


def save_pom(tree):
    """Saves the modified XML tree back to pom.xml."""
    indent(tree.getroot())
    tree.write("pom.xml", encoding="UTF-8", xml_declaration=True)
    print("✅ pom.xml updated successfully.")


def load_jproject():
    """
    Loads the jproject.json file from the .jpm directory.
    Returns None if the file does not exist.
    """
    if not os.path.exists(JPROJECT_FILE):
        return None
    with open(JPROJECT_FILE, "r") as f:
        return json.load(f)


def save_jproject(data, artifact_id="."):
    """
    Saves the jproject.json file to the .jpm directory.
    This will be called during project initialization, before doing 'cd' into the project.

    Arguments:
        artifact_id: The artifact ID of the project (used for directory structure).
        data: The data to save in the jproject.json file.
    """
    ensure_jpm_dir(artifact_id)
    with open(os.path.join(artifact_id, JPROJECT_FILE), "w") as f:
        json.dump(data, f, indent=2)


def ensure_jpm_dir(artifact_id):
    """
    Ensures that the .jpm directory exists, inside the given artifact_id directory.
    """
    if not os.path.exists(os.path.join(artifact_id, JPM_DIR)):
        os.makedirs(os.path.join(artifact_id, JPM_DIR))


def cache_spring_metadata(metadata, artifact_id="."):
    """
    Caches Spring Boot metadata to a JSON file.
    This will be called during project initialization, before doing 'cd' into the project.

    Arguments:
        artifact_id: The artifact ID of the project (used for directory structure).
        metadata: The metadata dictionary to cache.
    """
    ensure_jpm_dir(artifact_id)
    with open(os.path.join(artifact_id, SPRING_CACHE_FILE), "w") as f:
        json.dump(metadata, f)


def get_cached_spring_metadata():
    """Retrieves cached Spring Boot metadata from the JSON file.
    """
    if os.path.exists(SPRING_CACHE_FILE):
        with open(SPRING_CACHE_FILE, "r") as f:
            return json.load(f)
    return {}  # Return empty if no cache


def get_spring_metadata():
    """
    Fetches the dependency map from Spring. 
    You should cache this in a local file (e.g., ~/.jpm/spring_cache.json)
    """
    headers = {'Accept': 'application/vnd.initializr.v2.2+json'}
    try:
        response = requests.get(
            "https://start.spring.io/metadata/client", headers=headers, verify=True)
        data = response.json()

        # Flatten the nested categories into a simple lookup map
        mapping = {}
        for category in data['dependencies']['values']:
            for dep in category['values']:
                mapping[dep['id']] = dep['name']
        return mapping
    except:
        return {}


def get_pom_content(group_id, artifact_id, version, java_version):
    return f"""<project xmlns="http://maven.apache.org/POM/4.0.0"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
      
      <modelVersion>4.0.0</modelVersion>
      <groupId>{group_id}</groupId>
      <artifactId>{artifact_id}</artifactId>
      <version>{version}</version>
      
      <properties>
        <maven.compiler.release>{java_version}</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.version>5.10.2</junit.version>
      </properties>
      
      <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${{junit.version}}</version>
            <scope>test</scope>
        </dependency>
      </dependencies>

      <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-shade-plugin</artifactId>
                <version>3.5.2</version>
                <executions>
                    <execution>
                        <phase>package</phase>
                        <goals>
                            <goal>shade</goal>
                        </goals>
                        <configuration>
                            <transformers>
                                <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                                    <mainClass>{group_id}.App</mainClass>
                                </transformer>
                            </transformers>
                            <filters>
                                <filter>
                                    <artifact>*:*</artifact>
                                    <excludes>
                                        <exclude>META-INF/*.SF</exclude>
                                        <exclude>META-INF/*.DSA</exclude>
                                        <exclude>META-INF/*.RSA</exclude>
                                    </excludes>
                                </filter>
                            </filters>
                        </configuration>
                    </execution>
                </executions>
            </plugin>

            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
        </plugins>
      </build>
    </project>"""


def get_main_class_content(group_id):
    """
    Returns the content of a basic Java main class (App.java).
    Using inspect.cleandoc removes the leading indentation automatically.
    """
    content = f"""package {group_id};

public class App {{
    public static void main(String[] args) {{
        System.out.println("`jpm` is awesome 🚀!");
        System.out.println("Hello, World!");
    }}
}}"""
    return content


def get_test_class_content(group_id):
    """
    Returns the content of a basic Java test class (AppTest.java) for JUnit 5.
    """
    content = f"""package {group_id};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class AppTest {{

    @Test
    public void testApp() {{
        assertTrue(true, "This test should always pass");
    }}
}}"""
    return content


def get_version_info():
    """
    Returns detailed version and environment info for JPM, Java, and OS.
    """
    # Get Java version
    try:
        java_version = subprocess.check_output(["java", "-version"],
                                               stderr=subprocess.STDOUT).decode().splitlines()[0]
    except:
        java_version = "Not Found"

    info = [
        f'📦 Java Package Manager (JPM) Version: "{VERSION}" ({VERSION_DATE})',
        f"☕ Java Runtime: {java_version}",
        f'🖥️  Operating System: "{platform.system()} {platform.release()}", architecture: "{platform.machine()}"',
    ]

    return "\n".join(info)
