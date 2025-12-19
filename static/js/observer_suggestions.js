(() => {
    const observerInputs = document.querySelectorAll(".observer-input");
    const debounceHandles = new WeakMap();

    const hideList = (list) => {
        if (!list) return;
        list.classList.add("d-none");
        list.innerHTML = "";
    };

    const renderSuggestions = (list, items, input) => {
        if (!list) return;
        if (!items.length) {
            hideList(list);
            return;
        }
        list.innerHTML = items
            .map(
                (name) => `<button type="button" class="btn btn-sm observer-suggestion" data-observer-suggestion>${name}</button>`
            )
            .join("");
        list.classList.remove("d-none");
    };

    const fetchObservers = async (query, list, input) => {
        if (!query) {
            hideList(list);
            return;
        }
        try {
            const resp = await fetch(`/api/observers?q=${encodeURIComponent(query)}`);
            if (!resp.ok) {
                throw new Error("Failed to load observers");
            }
            const data = await resp.json();
            renderSuggestions(list, data.observers || [], input);
        } catch (err) {
            console.warn(err);
            hideList(list);
        }
    };

    const setupInput = (input) => {
        const wrapper = input.closest(".observer-field");
        if (!wrapper) return;
        let list = wrapper.querySelector(".observer-suggestions");
        if (!list) {
            list = document.createElement("div");
            list.className = "observer-suggestions d-none";
            wrapper.appendChild(list);
        }
        const scheduleFetch = () => {
            const value = input.value.trim();
            if (debounceHandles.has(input)) {
                clearTimeout(debounceHandles.get(input));
            }
            const handle = setTimeout(() => fetchObservers(value, list, input), 350);
            debounceHandles.set(input, handle);
        };
        input.addEventListener("input", scheduleFetch);
        input.addEventListener("focus", scheduleFetch);
        list.addEventListener("click", (ev) => {
            const target = ev.target.closest("[data-observer-suggestion]");
            if (!target) return;
            input.value = target.textContent.trim();
            hideList(list);
        });
    };

    observerInputs.forEach(setupInput);

    document.addEventListener("click", (event) => {
        const target = event.target;
        observerInputs.forEach((input) => {
            const wrapper = input.closest(".observer-field");
            const list = wrapper ? wrapper.querySelector(".observer-suggestions") : null;
            if (!list || list.contains(target) || input === target) {
                return;
            }
            hideList(list);
        });
    });
})();
