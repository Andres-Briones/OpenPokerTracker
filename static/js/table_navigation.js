let selectedRow = null;

function highlightRow(row) {
  row.classList.add('highlighted-row');
}

function unhighlightRow(row) {
  row.classList.remove('highlighted-row');
}

function setSelectedRow(row) {
  if (selectedRow) {
    unhighlightRow(selectedRow);
  }
  highlightRow(row);
  selectedRow = row;

  // Focus the row so that arrow keys work immediately
  setTimeout(() => row.focus(), 0);
}

function attachRowHandlers() {
  let rows = document.querySelectorAll('table tbody tr');
  rows.forEach(function(row) {
    if (!row.hasAttribute('tabindex')) {
      row.setAttribute('tabindex', '0');
      row.addEventListener('click', function() {
        setSelectedRow(row);
      });
    }
  });
  console.log("Row handlers attached. Total rows:", rows.length);
}

// Keyboard navigation for up/down and selecting with Enter
document.addEventListener('keydown', function(e) {
    if (!selectedRow) return;

    if (e.key === 'ArrowUp') {
        let prevRow = selectedRow.previousElementSibling;
        if (prevRow){
            prevRow.click(); 
            setSelectedRow(prevRow);
        }
    } else if (e.key === 'ArrowDown') {
        let nextRow = selectedRow.nextElementSibling;
        if (nextRow){
            nextRow.click();
            setSelectedRow(nextRow);
        }
    }// As there is a selected row, it means that the hand-replayer page is loaded. We want to navigate in the hand with the left and right arrows 
    else if (e.key === 'ArrowLeft') {
        // Simulate a click on the previous button
        const prevButton = document.getElementById('previous-button');
        if (prevButton) {
            prevButton.click();
        }
    } else if (e.key === 'ArrowRight') {
        // Simulate a click on the next button
        const nextButton = document.getElementById('next-button');
        if (nextButton) {
            nextButton.click();
        }
    }
});

// On initial load, attach event handlers
document.addEventListener('DOMContentLoaded', function() {
  attachRowHandlers();
});

// When HTMX adds new rows, reattach handlers to new elements
document.body.addEventListener('htmx:afterSwap', function(event) {
  attachRowHandlers();
});
