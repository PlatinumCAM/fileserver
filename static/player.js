    let playlist = [];
    let currentIndex = -1;
    let autoPlay = true;
    let shuffle = false;

    const playerContainer = document.getElementById('player-container');
    const player = document.getElementById('audio-player');
    const coverImg = document.getElementById('cover');
    const songTitle = document.getElementById('song-title');
    const albumName = document.getElementById('album-name');
    const autoBtn = document.getElementById('auto-btn');
    const themeBtn = document.getElementById('theme-btn');
    const shuffleBtn = document.getElementById('shuffle-btn');
    const loopBtn = document.getElementById('loop-btn');

    // Volume
    const savedVolume = localStorage.getItem('preferredVolume');
    player.volume = savedVolume ? parseFloat(savedVolume) : 0.5;
    player.addEventListener('volumechange', () => {
      localStorage.setItem('preferredVolume', player.volume.toString());
    });

    // Thème
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
      document.body.classList.add('dark');
      themeBtn.textContent = 'Mode clair';
    }

    function toggleTheme() {
      const dark = document.body.classList.toggle('dark');
      localStorage.setItem('theme', dark ? 'dark' : 'light');
      themeBtn.textContent = dark ? 'Mode clair' : 'Mode sombre';
    }

    // Playlist
    document.querySelectorAll('.file-row').forEach(row => {
      if(row.dataset.mp3 === "1") {
        playlist.push({
          src: row.dataset.src,
          cover: row.dataset.cover,
          name: row.dataset.name,
          album: row.dataset.album
        });
      }
    });

    function playAudio(src, cover, title, album) {
        currentIndex = playlist.findIndex(f => f.src === src);
        player.src = src;
        player.loop = false;
        loopBtn.textContent = "🔁 Non";
        songTitle.textContent = title;  // déjà sans extension
        albumName.textContent = album || "";
        coverImg.src = cover;
        playerContainer.style.display = 'flex';
        player.play().catch(() => {});
        }
    function nextTrack() {
      if (playlist.length === 0) return;
      let nextIndex;
      if(shuffle) {
        nextIndex = Math.floor(Math.random() * playlist.length);
      } else {
        nextIndex = (currentIndex + 1) % playlist.length;
      }
      const next = playlist[nextIndex];
      playAudio(next.src, next.cover, next.name, next.album);
    }

    function prevTrack() {
      if (playlist.length === 0) return;
      const prevIndex = (currentIndex - 1 + playlist.length) % playlist.length;
      const prev = playlist[prevIndex];
      playAudio(prev.src, prev.cover, prev.name, prev.album);
    }

    function playNext() { if(autoPlay) nextTrack(); }

    function toggleAutoPlay() {
      autoPlay = !autoPlay;
      autoBtn.classList.toggle('active', autoPlay);
      autoBtn.textContent = "Lecture auto : " + (autoPlay ? "ON" : "OFF");
    }

    function toggleShuffle() {
      shuffle = !shuffle;
      shuffleBtn.textContent = shuffle ? "🔀 Aléatoire" : "🔀 Normal";
    }

    function toggleLoop() {
      player.loop = !player.loop;
      loopBtn.textContent = player.loop ? "🔁 Oui" : "🔁 Non";
    }

    player.addEventListener('ended', playNext);