/**
 * Shared JavaScript for The Mubi 1000
 */

// API base URL (extracted from body data attribute, trailing slash stripped)
const BASE = document.body.dataset.apiBase.replace(/\/$/, '');

/**
 * Fetch wrapper with error handling.
 * Returns parsed JSON on success, or throws an Error on failure.
 */
async function apiFetch(url) {
    const response = await fetch(url);
    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'An error occurred');
    }
    return response.json();
}

/**
 * Create a movie card HTML string.
 *
 * @param {Object} movie - Movie data object
 * @param {Object} [options] - Display options
 * @param {boolean} [options.showDirector=true] - Show director link
 * @param {boolean} [options.showCountry=true] - Show country link
 * @returns {string} HTML string for the card
 */
function createMovieCardHTML(movie, options) {
    const showDirector = !options || options.showDirector !== false;
    const showCountry = !options || options.showCountry !== false;

    return `
        <div class="movie-card border border-gray-700 rounded-lg p-4 ${movie.watched ? 'watched' : ''}">
            <div class="flex justify-between items-start mb-2">
                <span class="text-lg font-bold text-gray-100">#${movie.rank}</span>
                ${movie.watched ? '<span class="text-xs bg-gray-600 text-white px-2 py-1 rounded">Watched</span>' : ''}
            </div>
            <h3 class="font-semibold text-gray-100 mb-2">${movie.title}</h3>
            <div class="space-y-1">
                ${showDirector && movie.director ? `<p class="text-sm text-gray-400"><span class="font-medium">Director:</span> <a href="${BASE}/director/${encodeURIComponent(movie.director)}" class="text-blue-400 hover:text-blue-300">${movie.director}</a></p>` : ''}
                ${showCountry && movie.country ? `<p class="text-sm text-gray-400"><span class="font-medium">Country:</span> <a href="${BASE}/country/${encodeURIComponent(movie.country)}" class="text-blue-400 hover:text-blue-300">${movie.country}</a></p>` : ''}
                ${movie.year ? `<p class="text-sm text-gray-400"><span class="font-medium">Year:</span> ${movie.year}</p>` : ''}
                ${movie.streaming_services_full && movie.streaming_services_full.length > 0
                    ? `<p class="text-sm text-gray-400"><span class="font-medium">Streaming:</span> <span class="text-green-400">${movie.streaming_services_full.map(s => s.name).join(', ')}</span></p>`
                    : ''}
            </div>
            ${movie.url ? `<a href="https://mubi.com${movie.url}" target="_blank" class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">View on Mubi</a>` : ''}
        </div>
    `;
}

/**
 * Display a random movie in the standard random-movie section.
 *
 * @param {Object} movie - Movie data
 * @param {Function} getAnotherFn - Callback for the "Get Another" button
 */
function displayRandomMovie(movie, getAnotherFn) {
    const section = document.getElementById('randomMovieSection');
    const content = document.getElementById('randomMovieContent');

    window._getAnotherRandom = getAnotherFn;

    content.innerHTML = `
        <div class="text-center">
            <div class="text-6xl font-bold text-blue-400 mb-4">#${movie.rank}</div>
            <h3 class="text-3xl font-bold mb-4 text-gray-100">${movie.title}</h3>
            <div class="space-y-2 mb-4">
                ${movie.director ? `<p class="text-xl text-gray-300"><span class="font-medium">Directed by:</span> <a href="${BASE}/director/${encodeURIComponent(movie.director)}" class="text-blue-400 hover:text-blue-300">${movie.director}</a></p>` : ''}
                ${movie.country ? `<p class="text-lg text-gray-300"><span class="font-medium">Country:</span> <a href="${BASE}/country/${encodeURIComponent(movie.country)}" class="text-blue-400 hover:text-blue-300">${movie.country}</a></p>` : ''}
                ${movie.year ? `<p class="text-lg text-gray-300"><span class="font-medium">Year:</span> ${movie.year}</p>` : ''}
                ${movie.streaming_services_full && movie.streaming_services_full.length > 0
                    ? `<p class="text-lg text-gray-300"><span class="font-medium">Streaming on:</span> <span class="text-green-400">${movie.streaming_services_full.map(s => s.name).join(', ')}</span></p>`
                    : ''}
            </div>
            ${movie.watched ? '<p class="text-lg text-orange-400 font-semibold mb-4">You have already watched this movie!</p>' : ''}
            <div class="space-x-4">
                ${movie.url ? `<a href="https://mubi.com${movie.url}" target="_blank" class="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">View on Mubi</a>` : ''}
                <button onclick="window._getAnotherRandom()" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
                    Get Another Random Movie
                </button>
            </div>
        </div>
    `;

    section.style.display = 'block';
    section.classList.remove('hidden');
}
