import boto3
import tempfile
import os
import shutil
import configparser
from subprocess import check_output, CalledProcessError, call
from git import Repo

config = configparser.ConfigParser()
config.read('config.ini')
ANDROID_TOOLS_HOME = config['DEFAULT']['AndroidToolsHome']
GRADLE_VERSION = config['DEFAULT']['GradleVersion']
ANDROID_TARGET_VERSION = config['DEFAULT']['AndroidTargetVersion']
TEMP_APP_SRC = config['DEFAULT']['TmpAppSrc']
CODEBUILD_SERVICE_ROLE = config['AWS']['CodeBuildServiceRole']
S3_BUCKET = config['AWS']['S3Bucket']


def create_code_build_project(appName, description='', *args):
    codecommit_url = 'https://git-codecommit.us-east-1.amazonaws.com/v1/repos/' + appName
    client = boto3.client('codebuild')
    response = client.create_project(
        name=appName,
        description=description,
        source={
            'type': 'CODECOMMIT',
            'location': codecommit_url,
            'buildspec': 'buildspec.yml'
        },
        artifacts={
            'type': 'S3',
            'location': 'arn:aws:s3:::' + S3_BUCKET
        },
        environment={
            'type': 'LINUX_CONTAINER',
            'image': 'aws/codebuild/android-java-8:24.4.1',
            'computeType': 'BUILD_GENERAL1_SMALL',
            'environmentVariables': [],
            'privilegedMode': False
        },
        serviceRole=CODEBUILD_SERVICE_ROLE
    )
    print(response)


def build_project(projectName):
    client = boto3.client('codebuild')
    response = client.start_build(projectName=projectName)
    print(response)
    return response['build']['id']


def get_buildlogs(projectId, startTime=0):
    projectName, logStreamName = projectId.split(':')
    logGroupName = '/aws/codebuild/' + projectName
    client = boto3.client('logs')
    logEvents = client.get_log_events(logGroupName=logGroupName, logStreamName=logStreamName, startTime=startTime)
    print(logEvents)
    return logEvents


def install_apk(projectName, apkPath, androidPath=''):
    # download apk from s3
    s3 = boto3.resource('s3')
    s3.meta.client.download_file(S3_BUCKET, projectName + '/app-debug.apk', 'app-debug.apk')
    installCmd = ['adb', 'install', '-r', 'app-debug.apk']
    result = _exec_cmd(installCmd)
    print(result)


def _generate_build_gradle(packageName, applicationName, projectPath):
    templateScript = '''apply plugin: 'com.android.application'

android {{
    compileSdkVersion 26
    buildToolsVersion "26.0.1"
    defaultConfig {{
        applicationId "{}.{}"
        minSdkVersion 21
        targetSdkVersion 26
        versionCode 1
        versionName "1.0"
        testInstrumentationRunner "android.support.test.runner.AndroidJUnitRunner"
    }}
    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }}
    }}
}}

dependencies {{
    implementation fileTree(dir: 'libs', include: ['*.jar'])
    implementation 'com.android.support:appcompat-v7:26.1.0'
    implementation 'com.android.support.constraint:constraint-layout:1.0.2'
    testImplementation 'junit:junit:4.12'
    androidTestImplementation('com.android.support.test.espresso:espresso-core:3.0.1', {{
        exclude group: 'com.android.support', module: 'support-annotations'
    }})
}}
'''
    gradlePath = os.path.join(projectPath, 'app', 'build.gradle')
    finalScript = templateScript.format(packageName, applicationName)
    with open(gradlePath, 'w') as f:
        f.write(finalScript)


def _generate_project_src(packageName, applicationName, projectPath):
    androidBinPath = os.path.join(ANDROID_TOOLS_HOME, 'android')
    createProjectScript = [androidBinPath, 'create', 'project', '--gradle', '--gradle-version', '3.0.0', '--activity', 'Main', '--package', packageName + '.' + applicationName, '--target', 'android-26', '--path', './tmp']
    result = _exec_cmd(createProjectScript)


def _generate_project_meta(projectPath):
    # copy template project to project path
    shutil.copytree('./AndroidTemplateApplication', projectPath)

    # copy generated src file to project path
    shutil.copytree(os.path.join(TEMP_APP_SRC, 'src'), os.path.join(projectPath, 'app', 'src'))

    # delete generated src
    shutil.rmtree(TEMP_APP_SRC)


def generate_project(packageName, applicationName, projectPath):
    _generate_project_src(packageName, applicationName, projectPath)
    _generate_project_meta(projectPath)
    _generate_build_gradle(packageName, applicationName, projectPath)


def _exec_cmd(cmd):
    t = tempfile.TemporaryFile()
    try:
        output = check_output(cmd, stderr=t)
    except CalledProcessError as e:
        t.seek(0)
        result = e.returncode, t.read()
    else:
        result = 0, output
    return result


def create_remote_repo(appName, description=''):
    client = boto3.client('codecommit')
    response = client.create_repository(
        repositoryName=appName,
        repositoryDescription=description
    )
    print(response)


def delete_remote_repo(appName):
    client = boto3.client('codecommit')
    response = client.delete_repository(
        repositpryName=appName
    )
    print(response)


def local_repo(appName, projectPath):
    file_list = os.listdir(projectPath)
    if '.git' in file_list:
        file_list.remove('.git')
    remote_path = 'https://git-codecommit.us-east-1.amazonaws.com/v1/repos/'+ appName
    repo = Repo.init(projectPath)
    repo.index.add(file_list)
    repo.index.commit("init")
    os.chdir(projectPath)
    command = ['git', 'push', remote_path, '--all']
    result = _exec_cmd(command)
    os.chdir('./')


def init_project(packageName, appName, projectPath, description=''):
    generate_project(packageName, appName, projectPath)
    create_remote_repo(appName, description)
    local_repo(appName, projectPath)
    create_code_build_project(appName)


def main():
    # projectName = 'android-test-2'
    # build_project('android-build-sdk-base')
    buildId = 'helloapp:cf89cb11-4b23-40ef-a55b-61b414f2d5e1'
    packageName = 'com.rexz'
    appName = 'helloapp'
    projectPath = os.path.join('./', appName)
    # print(build_project(appName))
    # init_project(packageName, appName, projectPath)
    get_buildlogs(buildId, 1510031877000)
    # install_apk('', '')
    # generate_project(packageName, appName, os.path.join('./', appName))


if __name__ == '__main__':
    main()
