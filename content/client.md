---
---

# YuGiOh Access Client

### Beta Testing Trailer

<iframe src="https://www.youtube.com/embed/R1_Syp7CrqY?modestbranding=1&rel=0" width="560" height="315" title="YuGiOh Access (The Client) - Cinematic Audio Trailer" frameborder="0" allow="accelerometer;  clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

### Intro

Welcome duelists. Grab your duel disks and get ready to duel.

YuGiOhAccess (The Client) is a game for Desktop that allows you to play the YuGiOh Trading Card Game either against an AI opponent, against a friend or online against other players, both sighted and blind.


### Notable Features

* Fully accessible. The client is build by the community for the community, and is fully accessible to blind and visually impaired players.
* Play against a bot opponent, or other players.
* Play online against other players, both sighted and blind.
* Features an immersive sound design, with sound effects and music.
* Play with the latest cards, including cards from the latest sets.
* Help shape the future of YuGiOhAccess by providing feedback and suggestions.

### Beta Testing

The beta is now available for download. Click the button below to download the client and start playing.

<div id="download-section">
  <div id="download-loading" style="display: block;">
    <p>Loading latest release...</p>
  </div>
  <div id="download-error" style="display: none;">
    <p>Unable to load latest release. Please visit <a href="https://github.com/yugiohaccess/yugiohaccess/releases/latest">GitHub Releases</a> to download manually.</p>
  </div>
  <div id="download-options" style="display: none;">
    <h4 id="version-info"></h4>
    <div style="margin: 20px 0;">
      <h5>Windows</h5>
      <div style="margin: 10px 0;">
        <a id="win-installer" role="button" class="btn btn-primary" style="margin-right: 10px;">Windows Installer (.exe)</a>
        <a id="win-portable" role="button" class="btn btn-secondary">Windows Portable (.zip)</a>
      </div>
      <h5>macOS</h5>
      <div style="margin: 10px 0;">
        <a id="mac-installer" role="button" class="btn btn-primary" style="margin-right: 10px;">macOS Installer (.pkg)</a>
        <a id="mac-portable" role="button" class="btn btn-secondary">macOS Portable (.zip)</a>
      </div>
    </div>
    <p><small>All downloads are from the latest release on <a href="https://github.com/yugiohaccess/yugiohaccess/releases">GitHub</a>.</small></p>
  </div>
</div>

<script>
async function loadLatestRelease() {
  try {
    // Check for cached data first
    const cacheKey = 'yugiohaccess-latest-release';
    const cacheTimestampKey = 'yugiohaccess-cache-timestamp';
    const cacheExpiry = 6 * 60 * 60 * 1000; // 6 hours in milliseconds
    
    const cachedData = localStorage.getItem(cacheKey);
    const cacheTimestamp = localStorage.getItem(cacheTimestampKey);
    
    if (cachedData && cacheTimestamp) {
      const now = Date.now();
      const cacheAge = now - parseInt(cacheTimestamp);
      
      if (cacheAge < cacheExpiry) {
        // Use cached data
        const release = JSON.parse(cachedData);
        updateDownloadOptions(release);
        return;
      }
    }
    
    // Fetch fresh data from GitHub API
    const response = await fetch('https://api.github.com/repos/yugiohaccess/yugiohaccess/releases/latest');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const release = await response.json();
    
    // Cache the response
    localStorage.setItem(cacheKey, JSON.stringify(release));
    localStorage.setItem(cacheTimestampKey, Date.now().toString());
    
    updateDownloadOptions(release);
    
  } catch (error) {
    console.error('Error loading latest release:', error);
    document.getElementById('download-loading').style.display = 'none';
    document.getElementById('download-error').style.display = 'block';
  }
}

function updateDownloadOptions(release) {
  try {
    
    // Find the assets we need
    const assets = release.assets;
    const downloads = {
      winInstaller: assets.find(a => a.name.includes('win-Setup.exe')),
      winPortable: assets.find(a => a.name.includes('win-Portable.zip')),
      macInstaller: assets.find(a => a.name.includes('osx-Setup.pkg')),
      macPortable: assets.find(a => a.name.includes('osx-Portable.zip'))
    };
    
    // Update version info
    document.getElementById('version-info').textContent = `Latest Version: ${release.tag_name}`;
    
    // Set download links
    if (downloads.winInstaller) {
      document.getElementById('win-installer').href = downloads.winInstaller.browser_download_url;
    } else {
      document.getElementById('win-installer').style.display = 'none';
    }
    
    if (downloads.winPortable) {
      document.getElementById('win-portable').href = downloads.winPortable.browser_download_url;
    } else {
      document.getElementById('win-portable').style.display = 'none';
    }
    
    if (downloads.macInstaller) {
      document.getElementById('mac-installer').href = downloads.macInstaller.browser_download_url;
    } else {
      document.getElementById('mac-installer').style.display = 'none';
    }
    
    if (downloads.macPortable) {
      document.getElementById('mac-portable').href = downloads.macPortable.browser_download_url;
    } else {
      document.getElementById('mac-portable').style.display = 'none';
    }
    
    // Show download options
    document.getElementById('download-loading').style.display = 'none';
    document.getElementById('download-options').style.display = 'block';
    
  } catch (error) {
    console.error('Error updating download options:', error);
    document.getElementById('download-loading').style.display = 'none';
    document.getElementById('download-error').style.display = 'block';
  }
}

// Load release info when page loads
document.addEventListener('DOMContentLoaded', loadLatestRelease);
</script>


## News:

#### 2025-07-06

**Major Update: Open Source Release & New Updater System**

We're excited to announce several significant changes to YuGiOhAccess -  The Client:

**🎉 Now Open Source:** YuGiOhAccess is now fully open source and available on GitHub! The project is licensed under GPL-3.0.

**🚀 New Updater System:** We've migrated to a new updater system with enhanced features. **Important**: Users on the previous updater system will need to manually update once to transition to the new system.

**🔓 Open Beta:** The Discord requirement has been dropped to participate in the beta, and anyone can download and play YuGiOhAccess without needing Discord access.

After this one-time manual update, future updates will be seamless through the new system. Visit our [GitHub repository](https://github.com/yugiohaccess/yugiohaccess) to view the source code, report issues, or contribute to the project.

#### 2025-02-28

We are excited to announce that the beta testing phase for the YuGiOhAccess client has begun. We are looking for feedback and suggestions from the community, so please join our Discord server and let us know what you think.


#### 2025-01-04

We are excited to announce the release of the cinematic trailer for the YuGiOhAccess client, as well as announce that beta testing will begin soon. Stay tuned for more information.
