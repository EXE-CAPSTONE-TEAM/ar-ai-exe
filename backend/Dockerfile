# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG OPENMVS_REF=v2.4.0
ARG OPENMVS_BUILD_JOBS=2

FROM ${PYTHON_IMAGE} AS openmvs-builder
ARG OPENMVS_REF
ARG OPENMVS_BUILD_JOBS
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        libboost-graph-dev \
        libboost-iostreams-dev \
        libboost-program-options-dev \
        libboost-serialization-dev \
        libboost-system-dev \
        libceres-dev \
        libcgal-dev \
        libeigen3-dev \
        libglew-dev \
        libgl1-mesa-dev \
        libglu1-mesa-dev \
        libglfw3-dev \
        libjpeg-dev \
        libjxl-dev \
        libnanoflann-dev \
        libopencv-dev \
        libpng-dev \
        libtiff-dev \
        libtinygltf-dev \
        libtinyxml2-dev \
        ninja-build \
        nlohmann-json3-dev \
        pkg-config \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/build

RUN git clone --depth 1 --branch "${OPENMVS_REF}" https://github.com/cdcseacave/openMVS.git openMVS \
    && git clone --depth 1 https://github.com/cdcseacave/VCG.git vcglib \
    && sed -i 's/cv::IMWRITE_JPEGXL_QUALITY/cv::IMWRITE_JPEG_QUALITY/g' openMVS/libs/Common/Types.inl \
    && grep -RIl 'nanoflann::SearchParameters' openMVS | xargs sed -i 's/nanoflann::SearchParameters/nanoflann::SearchParams/g' \
    && grep -RIl 'SearchParams searchParams(0, false)' openMVS | xargs sed -i 's/SearchParams searchParams(0, false)/SearchParams searchParams(0, 0, false)/g' \
    && grep -RIl 'CGAL/AABB_traits_3.h' openMVS | xargs sed -i 's|CGAL/AABB_traits_3.h|CGAL/AABB_traits.h|g' \
    && grep -RIl 'CGAL/AABB_triangle_primitive_3.h' openMVS | xargs sed -i 's|CGAL/AABB_triangle_primitive_3.h|CGAL/AABB_triangle_primitive.h|g' \
    && cmake -S openMVS -B openMVS-build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/openmvs \
        -DVCG_ROOT=/opt/build/vcglib \
        -DOpenMVS_BUILD_TOOLS=ON \
        -DOpenMVS_BUILD_VIEWER=OFF \
        -DOpenMVS_USE_BREAKPAD=OFF \
        -DOpenMVS_USE_CERES=ON \
        -DOpenMVS_USE_CUDA=OFF \
        -DOpenMVS_USE_PYTHON=OFF \
        -DOpenMVS_ENABLE_IPO=OFF \
        -DOpenMVS_ENABLE_TESTS=OFF \
    && cmake --build openMVS-build --parallel "${OPENMVS_BUILD_JOBS}" \
    && cmake --install openMVS-build \
    && for binary in InterfaceCOLMAP DensifyPointCloud ReconstructMesh RefineMesh TextureMesh; do \
        ln -s "/opt/openmvs/bin/OpenMVS/$binary" "/opt/openmvs/bin/$binary"; \
    done \
    && test -x /opt/openmvs/bin/InterfaceCOLMAP \
    && test -x /opt/openmvs/bin/DensifyPointCloud \
    && test -x /opt/openmvs/bin/ReconstructMesh \
    && test -x /opt/openmvs/bin/RefineMesh \
    && test -x /opt/openmvs/bin/TextureMesh

FROM ${PYTHON_IMAGE} AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENMVS_BIN_DIR=/opt/openmvs/bin \
    COLMAP_BIN=colmap \
    BLENDER_BIN=blender \
    FFMPEG_BIN=ffmpeg \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2 \
    QT_QPA_PLATFORM=offscreen \
    LD_LIBRARY_PATH="/opt/openmvs/lib:${LD_LIBRARY_PATH}" \
    PATH="/opt/openmvs/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        blender \
        ca-certificates \
        colmap \
        ffmpeg \
        libboost-graph-dev \
        libboost-iostreams-dev \
        libboost-program-options-dev \
        libboost-serialization-dev \
        libboost-system-dev \
        libceres-dev \
        libcgal-dev \
        libeigen3-dev \
        libglew-dev \
        libgl1 \
        libgl1-mesa-dev \
        libglib2.0-0 \
        libglu1-mesa-dev \
        libglfw3-dev \
        libgomp1 \
        libjpeg-dev \
        libopencv-dev \
        libpng-dev \
        libtiff-dev \
        libtinygltf-dev \
        libtinyxml2-dev \
        nlohmann-json3-dev \
        python3-numpy \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=openmvs-builder /opt/openmvs /opt/openmvs
RUN echo "/opt/openmvs/lib" > /etc/ld.so.conf.d/openmvs.conf \
    && ldconfig \
    && for binary in InterfaceCOLMAP DensifyPointCloud ReconstructMesh RefineMesh TextureMesh; do \
        ldd "/opt/openmvs/bin/$binary" | grep -q "not found" && exit 1 || true; \
    done

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
