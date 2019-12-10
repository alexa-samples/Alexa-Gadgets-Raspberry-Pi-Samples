#!/bin/bash
# Shell script for ask-cli pre-deploy hook for Python
# Script Usage: pre_deploy_hook.sh <SKILL_NAME> <DO_DEBUG> <TARGET>
 
# SKILL_NAME is the preformatted name passed from the CLI, after removing special characters.
# DO_DEBUG is boolean value for debug logging
# TARGET is the deploy TARGET provided to the CLI. (eg: all, skill, lambda etc.)
 
# Run this script under skill root folder
 
# The script does the following:
#  - Create a temporary 'lambda_upload' directories under each SOURCE_DIR folder
#  - Copy the contents of '<SKILL_NAME>/SOURCE_DIR' folder into '<SKILL_NAME>/SOURCE_DIR/lambda_upload'
#  - Copy the contents of site packages in $VIRTUALENV created in <SKILL_NAME>/.venv/ folder
#  - Update the location of this 'lambda_upload' folder to skill.json for zip and upload
 
SKILL_NAME=$1
DO_DEBUG=${2:-false}
TARGET=${3:-"all"}
SKILL_ENV_NAME="skill_env"

SKILL_DIR=$SKILL_NAME
ENV_LOC="$SKILL_DIR/.venv/$SKILL_ENV_NAME"

if ! $DO_DEBUG ; then
    exec > /dev/null 2>&1
fi

install_dependencies() {
    # Install dependencies at lambda/py/requirements.txt
    return $(pip -q install -r lambda/requirements.txt -t lambda/skill_env/)
}

echo "###########################"
echo "Installing dependencies based on sourceDir"
grep "sourceDir" "skill.json" | cut -d: -f2 | sed 's/"//g' | sed 's/,//g' | while read -r SOURCE_DIR; do
    if install_dependencies $SOURCE_DIR; then
        echo "Codebase ($SOURCE_DIR) built successfully."
    else
        echo "There was a problem installing dependencies for ($SOURCE_DIR)."
        exit 1
    fi
done

echo "###########################"
echo "##### pre-deploy hook #####"
echo "###########################"
 
if [[ $TARGET == "all" || $TARGET == "lambda" ]]; then
    grep "sourceDir" ./skill.json | cut -d: -f2 | sed 's/"//g' | sed 's/,//g' | while read -r SOURCE_DIR; do
        # Step 1: Decide source path and upload path
        if [[ $SOURCE_DIR == */lambda_upload ]]; then
            ADJUSTED_SOURCE_DIR=${SOURCE_DIR%"/lambda_upload"}
            UPLOAD_DIR=$SOURCE_DIR
        else
            ADJUSTED_SOURCE_DIR=$SOURCE_DIR
            UPLOAD_DIR="$SOURCE_DIR/lambda_upload"
        fi
 
        # Step 2: Create empty lambda_upload folder
        echo "Checking for lambda_upload folder existence in sourceDir $ADJUSTED_SOURCE_DIR"
        rm -rf $UPLOAD_DIR
        mkdir $UPLOAD_DIR
 
        # Step 3: Copy source code in sourceDir to lambda_upload 
        echo "Copying source code in $ADJUSTED_SOURCE_DIR/$SKILL_ENV_NAME folder to $UPLOAD_DIR"
        rsync -avzq $ADJUSTED_SOURCE_DIR/$SKILL_ENV_NAME/* $UPLOAD_DIR

        # Step 4: Copy lambda code in sourceDir to lambda_upload 
        echo "Copying lambda code in $ADJUSTED_SOURCE_DIR/$SKILL_ENV_NAME folder to $UPLOAD_DIR"
        rsync -avzq --exclude '*lambda_upload' --exclude "*$SKILL_ENV_NAME" $ADJUSTED_SOURCE_DIR/* $UPLOAD_DIR
 
        # Step 5: Update the "manifest.apis.custom.endpoint.sourceDir" value in skill.json if necessary
        if ! [[ $SOURCE_DIR == */lambda_upload ]]; then
            echo "Updating sourceDir to point to lambda_upload folder in skill.json"
            RAW_SOURCE_DIR_LINE="\"sourceDir\": \"$SOURCE_DIR\""
            NEW_SOURCE_DIR_LINE="\"sourceDir\": \"$UPLOAD_DIR\""
            sed -in "s#$RAW_SOURCE_DIR_LINE#$NEW_SOURCE_DIR_LINE#g" ./skill.json
        fi
    done
    echo "###########################"
fi
 
exit 0
