import logging
import os
from typing import Callable, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/new", tags=["query"])


class DataResponse(BaseModel):
    code: int
    message: str
    data: Any


def create_new_graph_routes(
    args,
    api_key: Optional[str] = None,
    get_api_key_dependency: Optional[Callable] = None,
    get_working_dir_dependency: Optional[Callable] = None,
):
    # Setup logging
    logging.basicConfig(
        format="%(levelname)s:%(message)s", level=getattr(logging, args.log_level)
    )

    optional_api_key = get_api_key_dependency(api_key)
    optional_working_dir = get_working_dir_dependency(args)

    # 删除缓存
    @router.post("/resetcache", dependencies=[Depends(optional_api_key)])
    async def reset_cache(rag=Depends(optional_working_dir)):
        """Manually reset cache"""
        try:
            cachefile = rag.working_dir + "/kv_store_llm_response_cache.json"
            if os.path.exists(cachefile):
                with open(cachefile, "w") as f:
                    f.write("{}")
            return DataResponse(
                code=0,
                message=f"Manually reset cache successfully",
                data="ok",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


    # 知识图谱-实体修改
    @router.put(
        "/graph/entity/{entity_name}",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def update_entity(
        entity_name: str, entity_data: dict, rag=Depends(optional_working_dir)
    ):
        try:
            print("Updating entity:", entity_name)
            print("Entity data:", entity_data)
            new_entity_name = entity_data.get("entity_name", None)
            entity_type = entity_data.get("entity_type", None)
            description = entity_data.get("description", None)
            source_id = entity_data.get("source_id", None)
            # Prepare node data
            node_data = {
                "entity_type": entity_type,
                "description": description,
                "source_id": source_id,
            }
            # 如果new_entity_name存在，node_data中添加new_entity_name
            if new_entity_name:
                node_data["entity_name"] = new_entity_name

            await rag.aedit_entity(entity_name,node_data)
            new_entity_name = entity_name
            data = {"id": new_entity_name, "label": new_entity_name, **node_data}
            return DataResponse(code=0, message="ok", data=data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-实体删除
    @router.delete(
        "/graph/entity/{entity_name}",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def delete_entity(entity_name: str, rag=Depends(optional_working_dir)):
        print(f"Deleting entity {entity_name}")
        try:
            await rag.adelete_by_entity(entity_name)
            return DataResponse(code=0, message="ok", data=None)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-关系修改-通过开始节点和结束节点查询关系
    @router.put(
        "/graph/relation/by_nodes",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def update_relation_by_nodes(
        src_entity_name: str,
        tgt_entity_name: str,
        relation_data: dict,
        rag=Depends(optional_working_dir),
    ):
        try:
            src_id = src_entity_name
            tgt_id = tgt_entity_name
            weight = relation_data.get("weight", None)
            keywords = relation_data.get("keywords", None)
            description = relation_data.get("description", None)
            source_id = relation_data.get("source_id", None)

            edge_data = dict(
                weight=weight,
                description=description,
                keywords=keywords,
                source_id=source_id,
            )

            print("Edge Data:", edge_data)  # Debugging print
            # Insert node data into the knowledge graph
            await rag.aedit_relation(src_id, tgt_id, edge_data)
            data = {
                "id": src_id + "_" + tgt_id,
                "source": src_id,
                "target": tgt_id,
                **edge_data,
            }
            return DataResponse(code=0, message="ok", data=data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-关系删除-通过开始节点和结束节点查询关系
    @router.delete(
        "/graph/relation/by_nodes",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def delete_relation_by_nodes(
        src_entity_name: str, tgt_entity_name: str, rag=Depends(optional_working_dir)
    ):
        try:
            await rag.relationships_vdb.delete_entity_relation_by_nodes(
                src_entity_name, tgt_entity_name
            )
            relationships_to_delete = set()
            relationships_to_delete.add((src_entity_name, tgt_entity_name))
            rag.chunk_entity_relation_graph.remove_edges(list(relationships_to_delete))
            await rag.relationships_vdb.index_done_callback()
            await rag.chunk_entity_relation_graph.index_done_callback()
            return DataResponse(code=0, message="ok", data="")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-实体查询
    @router.get(
        "/graph/entity/{entity_name}",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def get_node(entity_name: str, rag=Depends(optional_working_dir)):
        try:
            node = await rag.chunk_entity_relation_graph.get_node(entity_name)
            return DataResponse(code=0, message="ok", data=node)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-关系查询-通过开始节点和结束节点查询关系
    @router.get(
        "/graph/relation/by_nodes",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def get_relation_by_nodes(
        src_entity_name: str, tgt_entity_name: str, rag=Depends(optional_working_dir)
    ):
        try:
            relation = await rag.chunk_entity_relation_graph.get_edge(
                src_entity_name, tgt_entity_name
            )
            return DataResponse(code=0, message="ok", data=relation)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-关系查询-通过节点ID查询关系
    @router.get(
        "/graph/relation/node/{node_id}",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def get_relation_by_node(node_id: str, rag=Depends(optional_working_dir)):
        try:
            relations = await rag.chunk_entity_relation_graph.get_node_edges(node_id)
            return DataResponse(code=0, message="ok", data=relations)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-实体列表-查询
    @router.get(
        "/graph/entity",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def get_graph_entity_list(rag=Depends(optional_working_dir)):
        try:
            # 提取所有实体和关系
            entities = await rag.chunk_entity_relation_graph.query_all()

            # 返回知识图谱数据
            return DataResponse(
                code=0,
                message="ok",
                data=entities,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 知识图谱-数据查询
    @router.get(
        "/graph/data",
        response_model=DataResponse,
        dependencies=[Depends(optional_api_key)],
    )
    async def get_graph_data(rag=Depends(optional_working_dir)):
        try:
            # 提取所有实体和关系
            entities = await rag.chunk_entity_relation_graph.query_all()
            # 返回知识图谱数据
            return DataResponse(code=0, message="ok", data=entities)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


    return router
