const apiUrl = 'http://127.0.0.1:5000/api/news';
let lastPublishedTime = null; // Tracks the last fetched article's published time
let currentPage = 1;
let fetchedPages = []; // Stores fetched pages for "Previous" functionality

const newsContainer = document.getElementById('news-container');
const prevButton = document.getElementById('prev-button');
const nextButton = document.getElementById('next-button');

// Fetch news articles from the backend
async function fetchNews() {
  let url = `${apiUrl}?`;
  if (lastPublishedTime) {
    url += `lastPublishedTime=${encodeURIComponent(lastPublishedTime)}`;
  }

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    const articles = await response.json();
    if (articles.length > 0) {
      lastPublishedTime = articles[articles.length - 1].published;
    }

    return articles;
  } catch (error) {
    console.error('Error fetching news:', error);
    alert('Failed to fetch news. Please try again later.');
    return [];
  }
}

// Render news articles
function renderNews(articles) {
  newsContainer.innerHTML = '';
  articles.forEach(article => {
    const newsItem = document.createElement('div');
    newsItem.classList.add('news-item');
    newsItem.innerHTML = `
      <div class="news-title">${article.title}</div>
      <div class="news-summary">${article.summary}</div>
      <a href="${article.link}" target="_blank">Read more</a>
    `;
    newsContainer.appendChild(newsItem);
  });
}

// Load the next page
async function loadNextPage() {
  const articles = await fetchNews();

  if (articles.length > 0) {
    // Store the current page's articles in fetchedPages
    fetchedPages.push(articles);

    renderNews(articles);
    currentPage++;
    prevButton.disabled = false; // Enable "Previous" button
  } else {
    alert('No more articles available.');
    nextButton.disabled = true; // Disable "Next" button when no more data is available
  }
}

// Load the previous page
function loadPrevPage() {
  if (currentPage > 1) {
    currentPage--;
    const previousArticles = fetchedPages[currentPage - 1];
    renderNews(previousArticles);

    // Update lastPublishedTime to match the current page
    lastPublishedTime = previousArticles[previousArticles.length - 1].published;

    nextButton.disabled = false; // Re-enable "Next" button
  }

  // Disable "Previous" button if on the first page
  prevButton.disabled = currentPage === 1;
}

// Event listeners for buttons
prevButton.addEventListener('click', loadPrevPage);
nextButton.addEventListener('click', loadNextPage);

// Load the first page
loadNextPage();
