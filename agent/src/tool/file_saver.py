import base64
import json
import os
import pickle
from typing import Optional, Sequence, Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    CheckpointTuple,
    Checkpoint,
    CheckpointMetadata,
    ChannelVersions,
)


class FileSaver(BaseCheckpointSaver[str]):
    def __init__(self, base_path: str = r"C:\Users\Administrator\Desktop\app\agent\checkpoint"):
        super().__init__()

        self.base_path = os.path.abspath(base_path)

        os.makedirs(base_path, exist_ok=True)

    def _get_checkpoint_path(self, thread_id):
        dir_path = os.path.join(self.base_path, thread_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, thread_id + ".json")
        return file_path

    def _serialize_checkpoint(self, data):
        pickled = pickle.dumps(data)
        return base64.b64encode(pickled).decode()

    def _deserialize_checkpoint(self, data):
        decoded = base64.b64decode(data)
        return pickle.loads(decoded)


    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Fetch the latest checkpoint tuple for the given thread_id.

        Returns None if no checkpoint exists.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_file_path = self._get_checkpoint_path(thread_id)

        if not os.path.exists(checkpoint_file_path):
            return None

        with open(checkpoint_file_path, "r", encoding="utf-8") as checkpoint_file:
            data = json.load(checkpoint_file)

        checkpoint = self._deserialize_checkpoint(data["checkpoint"])
        metadata = self._deserialize_checkpoint(data["metadata"])
        checkpoint_id = os.path.splitext(os.path.basename(checkpoint_file_path))[0]

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
        )



    def put(
            self,
            config: RunnableConfig,
            checkpoint: Checkpoint,
            metadata: CheckpointMetadata,
            new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Store a checkpoint with its configuration and metadata.

        Args:
            config: Configuration for the checkpoint.
            checkpoint: The checkpoint to store.
            metadata: Additional metadata for the checkpoint.
            new_versions: New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.

        Raises:
            NotImplementedError: Implement this method in your custom checkpoint saver.
        """
        #生成存储的json文件路径
        thread_id = config["configurable"]["thread_id"]
        os.makedirs(os.path.join(self.base_path, thread_id), exist_ok=True)
        checkpoint_id = checkpoint["id"]
        checkpoint_path = self._get_checkpoint_path(thread_id)
        #将Checkpoint进行序列化
        checkpoint_data = {
            "checkpoint": self._serialize_checkpoint(checkpoint),
            "metadata": self._serialize_checkpoint(metadata),
        }
        #将Checkpoint存储到文件系统
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        #生成返回值
        return {
            "configurable":{
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate writes linked to a checkpoint (no-op)."""
        return None

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Asynchronously fetch a checkpoint tuple using the given configuration."""
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Asynchronously store a checkpoint with its configuration and metadata."""
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Asynchronously store intermediate writes linked to a checkpoint."""
        return self.put_writes(config, writes, task_id, task_path)
