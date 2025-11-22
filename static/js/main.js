async function toggleSeat(element) {
    const seatId = element.dataset.id;
    const currentStatus = element.classList.contains('occupied') ? 'occupied' : 'free';
    const newStatus = currentStatus === 'free' ? 'occupied' : 'free';
    
    // Optimistic UI update
    element.classList.remove(currentStatus);
    element.classList.add(newStatus);
    
    try {
        const response = await fetch('/api/update_seat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                seat_id: seatId,
                status: newStatus
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // Revert if failed
            element.classList.remove(newStatus);
            element.classList.add(currentStatus);
            alert('Failed to update seat status');
        }
    } catch (error) {
        console.error('Error:', error);
        // Revert if error
        element.classList.remove(newStatus);
        element.classList.add(currentStatus);
        alert('Network error');
    }
}
