#!/bin/sh

package="rpm-bundle"
raw_github_url="https://raw.githubusercontent.com/nforro/$package/master"
gpg_key="$raw_github_url/repo/pubkey.gpg"
repository="deb $raw_github_url/repo/ /"

# download and import gpg key
wget -O - "$gpg_key" | sudo apt-key add - || exit 1

# add repo to sources.list
echo "$repository" | sudo tee -a /etc/apt/sources.list || exit 1

# refresh repository metadata
sudo apt-get -qq update || exit 1

# install package
sudo apt-get -y install "$package" || exit 1
