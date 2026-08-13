function renderICSection(container, label) {
    container.innerHTML = `
        <h3 class="text-lg font-semibold">${label}</h3>
        <label>Type:
            <select class="icType">
                <option value="constant">Constant</option>
                <option value="function">Function</option>
                <option value="gaussian">Gaussian</option>
            </select>
        </label>
        <div class="icOptions mt-2"></div>
  `;
    const select = container.querySelector(".icType");
    const optionsDiv = container.querySelector(".icOptions");
    select.addEventListener("change", () => updateICOptions(select.value, optionsDiv));
    updateICOptions(select.value, optionsDiv);
}

function updateICOptions(type, target) {
    if (type === "constant") {
        target.innerHTML = `<label>Value: <input type="number" step="any" class="icValue"></label>`;
    } else if (type === "function") {
        target.innerHTML = `<label>Expression: <input type="text" class="icExpr" placeholder="e.g. 0.1*sin(2*pi*x)*cos(2*pi*y)"></label>`;
    } else if (type === "gaussian") {
        target.innerHTML = `
            <label>Center: <input type="number" class="icCenterX" step="any">, 
            <input type="number" class="icCenterY" step="any"></label><br>
            <label>Sigma: <input type="number" class="icSigma" step="any"></label><br>
            <label>Amplitude: <input type="number" class="icAmplitude" step="any" value="1.0"></label>
        `;
    }
}

function renderBCSection(container) {
    container.innerHTML = `
        <h3 class="text-lg font-semibold">Boundary Conditions</h3>
        ${["left", "right", "top", "bottom"].map(side => `
                <label>${side}:
                <select class="bcType" data-side="${side}">
                    <option value="">None</option>
                    <option value="dirichlet">Dirichlet</option>
                    <option value="neumann0">Neumann</option>
                </select>
                <input type="number" step="any" class="bcValue" data-side="${side}" placeholder="Value">
                </label><br>
            `).join("")}
    `;
}

function extractIC(container) {
    const type = container.querySelector(".icType").value;
    if (type === "constant") {
        return { type, value: parseFloat(container.querySelector(".icValue").value) || 0 };
    } else if (type === "function") {
        return { type, expr: container.querySelector(".icExpr").value };
    } else if (type === "gaussian") {
        return {
            type,
            center: [
                parseFloat(container.querySelector(".icCenterX").value),
                parseFloat(container.querySelector(".icCenterY").value)
            ],
            sigma: parseFloat(container.querySelector(".icSigma").value),
            amplitude: parseFloat(container.querySelector(".icAmplitude").value) || 1.0
        };
    }
}

function extractBC(container) {
    const bc = {};
    ["left", "right", "top", "bottom"].forEach(side => {
        const type = container.querySelector(`.bcType[data-side="${side}"]`).value;
        const value = container.querySelector(`.bcValue[data-side="${side}"]`).value;
        if (type) {
            bc[side] = [type, parseFloat(value) || 0];
        }
    });
    return bc;
}

document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("equation-select");
    const forms = document.querySelectorAll(".sim-form");

    document.querySelectorAll(".ic-section").forEach(c => renderICSection(c, "Initial Condition (IC)"));
    document.querySelectorAll(".icv-section").forEach(c => renderICSection(c, "Initial Velocity (IC_v)"));
    document.querySelectorAll(".bc-section").forEach(c => renderBCSection(c));

    select.addEventListener("change", () => {
        forms.forEach(f => f.classList.add("hidden"));
        document.getElementById("form-" + select.value).classList.remove("hidden");
    });

    forms.forEach(form => {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const eq = form.id.replace("form-", "");
            const formData = new FormData(form);
            const params = Object.fromEntries(formData.entries());

            const icContainer = form.querySelector(".ic-section");
            if (icContainer) {
                params.ic = extractIC(icContainer);
            }

            const icvContainer = form.querySelector(".icv-section");
            if (icvContainer) {
                params.ic_v = extractIC(icvContainer);
            }

            const bcContainer = form.querySelector(".bc-section");
            if (bcContainer) {
                params.bc = extractBC(bcContainer);
            }

            let privateSim = params.private === "on";
            delete params.private;

            if (params.v_x && params.v_y) {
                params.v = [params.v_x, params.v_y];
                delete params.v_x;
                delete params.v_y;
            }

            Object.keys(params).forEach(k => {
                if (!isNaN(params[k])) params[k] = Number(params[k]);
            });

            const sim_params = {
                equation: eq,
                parameters: params,
                private: privateSim
            }

            const validateRes = await authFetch("/v1/simulations/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(sim_params)
            });

            const valJson = await validateRes.json();

            if (!validateRes.ok) {
                alert("Validation failed: " + JSON.stringify(valJson.detail?.Errors ?? valJson));
                return;
            }

            if (!valJson.stable || Object.keys(valJson.errors ?? {}).length > 0) {
                alert(`Stability: ${valJson.stable}, Errors: ${JSON.stringify(valJson.errors)}`);
                return;
            }

            const res = await authFetch("/v1/simulations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(sim_params)
            });

            if (!res.ok) {
                alert("Simulation submission failed");
                return;
            }
            const data = await res.json();
            alert("Simulation submitted! ID: " + data.simulation_id);
            window.location.href = "/simulations";
        })
    })
})